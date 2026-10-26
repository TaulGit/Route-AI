"""Repeatable offline graph checks; no LLM, map service, or network calls.

Run from the repository root:
    PYTHONPATH=backend backend/.venv/bin/python -m evals.run

The report measures scripted graph behavior and deterministic constraints. It
does not measure recommendation quality, factual freshness, or live API health.
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agents.v3.models import (
    EvidencePOI, PlanDraft, PlanStop, ResearchPlan, ResearchResult, ResearchTask,
    TravelBrief,
)
from app.agents.v3.workflow import build_graph


ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = Path(__file__).with_name("cases.json")


def complete_brief(**updates):
    data = {"city": "武汉", "date": "2026-11-07", "budget_max": 200,
            "max_pois": 3, "preferences": ["历史文化"]}
    data.update(updates)
    return TravelBrief(**data).model_dump()


def initial_state(brief=None):
    return {"brief": brief if brief is not None else complete_brief(),
            "mode": "demo", "provider": "deepseek", "status": "running"}


class FixtureProvider:
    """Deliberately scripted provider for testing the real LangGraph runtime."""

    def __init__(self, scenario="valid"):
        self.scenario = scenario
        self.research_plan_calls = 0
        self.research_calls = []
        self.propose_calls = []
        self.route_calls = []

    async def research_plan(self, brief):
        self.research_plan_calls += 1
        # The graph must assign its own unique IDs rather than drop a branch.
        return ResearchPlan(tasks=[ResearchTask(id="same", query="文化"),
                                   ResearchTask(id="same", query="自然")])

    async def research(self, brief, task):
        self.research_calls.append(task.id)
        if self.scenario == "all_branches_fail" or (
                self.scenario == "one_branch_fails" and task.id == "1"):
            raise RuntimeError("scripted research failure")
        if self.scenario == "malformed_evidence":
            return {"task_id": task.id, "pois": [{"id": "bad", "latitude": 999}]}
        prefix = "nature" if "自然" in brief.preferences else "culture"
        ids = ["a", "shared"] if task.id == "0" else ["shared", "c"]
        pois = [EvidencePOI(
            id=f"{prefix}-{suffix}", name=f"离线景点 {suffix}",
            longitude=114.3, latitude=30.5, visit_minutes=30,
            estimated_ticket_cost=0, source="fixture",
            fetched_at="2026-10-26T00:00:00+00:00",
        ) for suffix in ids]
        return ResearchResult(task_id=task.id, pois=pois, tool_calls=1,
                              diagnostics=["scripted fixture; not live evidence"])

    async def propose(self, brief, pois, feedback, attempt):
        self.propose_calls.append({"attempt": attempt, "feedback": list(feedback)})
        if self.scenario == "malformed_draft":
            return {"stops": [], "summary": "Invalid structured output"}
        if self.scenario == "provider_exception":
            raise RuntimeError("scripted generation failure")
        if self.scenario == "unknown_poi":
            ids = ["unretrieved-poi"]
        elif self.scenario == "duplicate_stop":
            ids = [pois[0].id, pois[0].id]
        elif self.scenario == "repairable_unknown_poi" and attempt == 1:
            ids = ["unretrieved-poi"]
        elif self.scenario == "over_stop_limit":
            ids = [poi.id for poi in pois]
        else:
            ids = [poi.id for poi in pois[:brief.max_pois]]
        return PlanDraft(stops=[PlanStop(poi_id=id_, visit_minutes=30) for id_ in ids],
                         summary="Scripted offline plan")

    async def route(self, brief, pois):
        self.route_calls.append([poi.id for poi in pois])
        if self.scenario == "route_exception":
            raise RuntimeError("scripted route failure")
        segments = [{"from_id": left.id, "to_id": right.id,
                     "duration_minutes": 5, "cost_estimate": 0,
                     "source": "fixture"} for left, right in zip(pois, pois[1:])]
        if self.scenario == "route_mismatch" and segments:
            segments[0]["from_id"] = "wrong-origin"
        return {"segments": segments, "warnings": ["Scripted offline route"]}


def load_cases():
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]


async def run_case(case):
    fixture = FixtureProvider(case.get("scenario", "valid"))
    graph = build_graph(InMemorySaver(), lambda *_: fixture)
    config = {"configurable": {"thread_id": f"offline-{case['id']}"}}
    checks = []
    started = perf_counter()

    def check(name, passed, detail=""):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    try:
        brief = complete_brief(**case.get("brief_updates", {}))
        if case.get("flow") == "clarify":
            result = await graph.ainvoke(initial_state({}), config)
            payload = result["__interrupt__"][0].value
            check("missing_fields_interrupt", payload.get("kind") == "clarify"
                  and set(payload.get("missing", [])) == {"city", "date", "budget_max"})
            check("no_research_before_clarification", fixture.research_plan_calls == 0)
            result = await graph.ainvoke(Command(resume={"brief": brief}), config)
        else:
            result = await graph.ainvoke(initial_state(brief), config)

        if case.get("flow") == "revise":
            check("first_plan_waits_for_review",
                  result.get("__interrupt__", [None])[0].value.get("kind") == "review")
            revised = complete_brief(preferences=["自然"])
            result = await graph.ainvoke(Command(resume={"action": "revise", "brief": revised}), config)
            check("revision_creates_new_generation", result.get("generation") == 2)
            check("revision_uses_fresh_evidence", all(p["id"].startswith("nature-")
                                                    for p in result.get("pois", [])))
            check("revision_keeps_two_current_branches", len(result.get("research_results", [])) == 2)

        expected = case["expected"]
        if expected["status"] in ("completed", "rejected"):
            interrupts = result.get("__interrupt__", [])
            check("valid_plan_waits_for_review", len(interrupts) == 1
                  and interrupts[0].value.get("kind") == "review")
            before_resume = len(fixture.propose_calls)
            action = "approve" if expected["status"] == "completed" else "reject"
            result = await graph.ainvoke(Command(resume={"action": action}), config)
            check("review_does_not_regenerate", len(fixture.propose_calls) == before_resume)
        else:
            check("invalid_plan_never_reaches_review", not result.get("__interrupt__"))
        check("final_status", result.get("status") == expected["status"],
              f"expected={expected['status']}, actual={result.get('status')}")
        check("proposal_attempts", result.get("proposal_attempts") == expected["attempts"],
              f"expected={expected['attempts']}, actual={result.get('proposal_attempts')}")
        check("branch_results_retained", len(result.get("research_results", [])) == 2)
        if "poi_count" in expected:
            check("deduplicated_evidence", len(result.get("pois", [])) == expected["poi_count"])
        if "violation_contains" in expected:
            violations = result.get("validation", {}).get("violations", [])
            check("expected_violation", any(expected["violation_contains"] in v for v in violations),
                  "; ".join(violations))
        if "failed_branch_count" in expected:
            failures = sum(any("检索分支失败" in d for d in r["diagnostics"])
                           for r in result.get("research_results", []))
            check("failed_branch_diagnostics", failures == expected["failed_branch_count"])
        if expected.get("no_route_calls"):
            check("untrusted_ids_never_reach_route", not fixture.route_calls)
        if case["scenario"] == "repairable_unknown_poi":
            check("validator_feedback_reaches_repair", len(fixture.propose_calls) == 2
                  and any("未检索到" in v for v in fixture.propose_calls[1]["feedback"]))
        observations = {"status": result.get("status"), "generation": result.get("generation"),
                        "proposal_attempts": result.get("proposal_attempts"),
                        "research_plan_calls": fixture.research_plan_calls,
                        "research_calls": len(fixture.research_calls),
                        "route_provider_calls": len(fixture.route_calls),
                        "violations": result.get("validation", {}).get("violations", [])}
    except Exception as exc:
        check("unexpected_exception", False, f"{type(exc).__name__}: {exc}")
        observations = {"exception_type": type(exc).__name__}
    return {"id": case["id"], "description": case["description"],
            "passed": bool(checks) and all(c["passed"] for c in checks),
            "elapsed_seconds": round(perf_counter() - started, 4),
            "checks": checks, "observations": observations}


async def evaluate(report_path):
    results = [await run_case(case) for case in load_cases()]
    passed = sum(case["passed"] for case in results)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Offline scripted-provider regression of the real LangGraph workflow",
        "network_calls": False,
        "checkpointer": "InMemorySaver (not a persistence/restart test)",
        "not_measured": ["LLM quality or success rate", "live Amap availability or factual freshness",
                         "production latency or concurrency", "cross-process checkpoint recovery"],
        "summary": {"cases": len(results), "passed": passed, "failed": len(results) - passed,
                    "checks": sum(len(c["checks"]) for c in results),
                    "checks_passed": sum(check["passed"] for case in results for check in case["checks"])},
        "results": results,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report_path), **report["summary"]}, ensure_ascii=False))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=ROOT / "docs" / "eval-report.json")
    args = parser.parse_args()
    report = asyncio.run(evaluate(args.report))
    raise SystemExit(1 if report["summary"]["failed"] else 0)


if __name__ == "__main__":
    main()
