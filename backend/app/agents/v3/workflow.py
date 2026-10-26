"""Plan → parallel tool agents → grounded proposal → validate/repair → review.

Only the research workers merge concurrent writes. Human interrupts have no
external side effects; resuming may safely re-enter the containing node.
"""

from functools import wraps
from time import perf_counter
from typing import Annotated, Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt

from .models import EvidencePOI, PlanDraft, ResearchPlan, ResearchTask, TravelBrief


def merge_results(left: dict, right: dict) -> dict:
    return {**left, **right}


class State(TypedDict, total=False):
    brief: dict
    mode: str
    provider: str
    status: str
    generation: int
    tasks: list[dict]
    results: Annotated[dict, merge_results]
    research_results: list[dict]
    pois: list[dict]
    draft: dict | None
    route: dict
    validation: dict
    feedback: list[str]
    proposal_attempts: int
    message: str
    task: dict
    planning_model_calls: int
    route_calls: int


def observed(name):
    """Emit real lifecycle boundaries, never model reasoning or prompts."""
    def decorate(fn):
        @wraps(fn)
        async def wrapped(state):
            writer = get_stream_writer()
            label = name
            if name == "research":
                label += ":" + state["task"]["id"]
            writer({"type": "node_start", "node": label, "message": f"开始 {label}"})
            start = perf_counter()
            result = await fn(state)
            writer({"type": "node_end", "node": label, "message": f"完成 {label}",
                    "data": {"elapsed_seconds": round(perf_counter() - start, 3)}})
            return result
        return wrapped
    return decorate


def required_fields(brief: TravelBrief) -> list[str]:
    return [key for key in ("city", "date", "budget_max")
            if getattr(brief, key) in (None, "")]


def validate_plan(brief: TravelBrief, draft: PlanDraft | None,
                  pois: list[EvidencePOI], route: dict) -> dict:
    """Check facts and feasibility in code, independently of the language model."""
    errors, warnings = [], list(route.get("warnings", []))
    by_id = {p.id: p for p in pois}
    stops = draft.stops if draft else []
    ids = [s.poi_id for s in stops]
    if not stops:
        errors.append("没有可执行的结构化行程")
    if len(ids) != len(set(ids)):
        errors.append("行程包含重复 POI")
    if any(i not in by_id for i in ids):
        errors.append("行程引用未检索到的 POI ID")
    if len(ids) > brief.max_pois:
        errors.append("景点数超过用户上限")
    segments = route.get("segments", [])
    if ids and len(segments) != len(ids) - 1:
        errors.append("缺少连续景点间的交通数据")
    for segment, (origin, destination) in zip(segments, zip(ids, ids[1:])):
        if (segment.get("from_id"), segment.get("to_id")) != (origin, destination):
            errors.append("交通数据与景点顺序不一致")
        if segment.get("duration_minutes", -1) < 0 or segment.get("cost_estimate", -1) < 0:
            errors.append("交通数据包含无效时长或费用")
        if segment.get("source") == "estimate":
            warnings.append("部分路段使用直线距离估算，出发前请核实真实交通")
    duration = sum(s.visit_minutes for s in stops) + sum(s.get("duration_minutes", 0) for s in segments)
    # Reserve lunch/break time and state explicitly that this is an estimate.
    duration += 60 if stops else 0
    cost = sum(by_id[i].estimated_ticket_cost for i in ids if i in by_id)
    cost += sum(s.get("cost_estimate", 0) for s in segments) + (60 if stops else 0)
    to_minutes = lambda t: int(t[:2]) * 60 + int(t[3:])
    available = to_minutes(brief.end_time) - to_minutes(brief.start_time)
    if duration > available:
        errors.append(f"预计耗时 {duration} 分钟超过可用 {available} 分钟")
    if brief.budget_max is not None and cost > brief.budget_max:
        errors.append(f"估算费用 {cost:.0f} 元超过预算 {brief.budget_max:.0f} 元")
    warnings.append("预留 60 分钟用餐/休息及 60 元餐费；门票和交通为估算，未含起终点接驳，未核实开放时间")
    if stops and any(by_id[i].source == "amap" for i in ids if i in by_id):
        warnings.append("高德 POI 检索不提供已核实票价；门票金额 0 表示未知，不能据此保证实际总价不超预算")
    if stops and any(by_id[i].source == "fixture" for i in ids if i in by_id):
        warnings.append("当前为离线示例数据，不代表实时景点、票价或路况")
    return {"feasible": not errors, "violations": list(dict.fromkeys(errors)),
            "warnings": list(dict.fromkeys(warnings)), "duration_minutes": duration,
            "cost_estimate": round(cost, 2)}


def build_graph(checkpointer, provider_factory):
    def provider(state):
        return provider_factory(state["mode"], state["provider"])

    @observed("clarify")
    async def clarify(state):
        brief = TravelBrief.model_validate(state["brief"])
        missing = required_fields(brief)
        while missing:
            answer = interrupt({"kind": "clarify", "missing": missing, "brief": brief.model_dump()})
            if answer.get("action") == "reject":
                return {"status": "rejected"}
            brief = TravelBrief.model_validate(answer["brief"])
            missing = required_fields(brief)
        return {"brief": brief.model_dump(), "status": "running"}

    @observed("research_plan")
    async def research_plan(state):
        result = ResearchPlan.model_validate(await provider(state).research_plan(TravelBrief(**state["brief"])))
        # Assign IDs ourselves: model-chosen duplicate IDs must not collapse branches.
        tasks = [ResearchTask(id=str(i), query=t.query).model_dump() for i, t in enumerate(result.tasks)]
        return {"tasks": tasks, "generation": state.get("generation", 0) + 1,
                "planning_model_calls": state.get("planning_model_calls", 0) + (state["mode"] == "live"),
                "proposal_attempts": 0, "feedback": [], "draft": None,
                "route": {}, "validation": {}}

    def fan_out(state):
        return [Send("research", {**state, "task": task}) for task in state["tasks"]]

    @observed("research")
    async def research(state):
        from .models import ResearchResult
        task = ResearchTask(**state["task"])
        try:
            import asyncio
            result = await asyncio.wait_for(
                provider(state).research(TravelBrief(**state["brief"]), task), timeout=120)
            result = ResearchResult.model_validate(result)
        except Exception as exc:
            # Failure of one worker is evidence of unavailability, not of a fake POI.
            result = ResearchResult(task_id=task.id, diagnostics=[f"检索分支失败 ({type(exc).__name__})"])
        return {"results": {f"{state['generation']}:{task.id}": result.model_dump()}}

    @observed("gather")
    async def gather(state):
        results = [state["results"][f"{state['generation']}:{task['id']}"] for task in state["tasks"]]
        unique = {}
        for result in results:
            for poi in result["pois"]:
                unique.setdefault(poi["id"], poi)
        return {"research_results": results, "pois": list(unique.values())}

    @observed("propose")
    async def propose(state):
        import asyncio
        attempt = state.get("proposal_attempts", 0) + 1
        try:
            if not state.get("pois"):
                raise ValueError("没有可用的真实 POI 证据")
            draft = await asyncio.wait_for(provider(state).propose(
                TravelBrief(**state["brief"]), [EvidencePOI(**p) for p in state["pois"]],
                state.get("feedback", []), attempt), timeout=90)
            result = {"draft": PlanDraft.model_validate(draft).model_dump()}
        except Exception as exc:
            result = {"draft": None, "feedback": [f"结构化生成失败 ({type(exc).__name__})"]}
        return {**result, "proposal_attempts": attempt,
                "planning_model_calls": state.get("planning_model_calls", 0) +
                    (state["mode"] == "live" and bool(state.get("pois")))}

    @observed("validate")
    async def validate(state):
        import asyncio
        brief = TravelBrief(**state["brief"])
        pois = [EvidencePOI(**p) for p in state.get("pois", [])]
        draft = PlanDraft(**state["draft"]) if state.get("draft") else None
        by_id = {p.id: p for p in pois}
        ids = [s.poi_id for s in draft.stops] if draft else []
        route = {"segments": [], "warnings": []}
        calls = 0
        if ids and len(ids) == len(set(ids)) and all(i in by_id for i in ids):
            calls = max(0, len(ids) - 1) if state["mode"] == "live" else 0
            try:
                route = await asyncio.wait_for(provider(state).route(brief, [by_id[i] for i in ids]), timeout=90)
            except Exception as exc:
                route["warnings"].append(f"交通数据不可用 ({type(exc).__name__})")
        report = validate_plan(brief, draft, pois, route)
        return {"route": route, "validation": report, "feedback": report["violations"],
                "route_calls": state.get("route_calls", 0) + calls}

    def after_validate(state):
        if state["validation"]["feasible"]:
            return "review"
        if state["proposal_attempts"] < 3 and state.get("pois"):
            return "propose"
        return "fail"

    @observed("review")
    async def review(state):
        answer = interrupt({"kind": "review", "brief": state["brief"],
                            "draft": state["draft"], "validation": state["validation"]})
        if answer["action"] == "revise":
            return {"brief": TravelBrief(**answer["brief"]).model_dump(), "status": "running"}
        return {"status": "completed" if answer["action"] == "approve" else "rejected"}

    async def fail(state):
        return {"status": "failed", "message": "达到修复上限，未能生成满足约束的行程；请调整预算、时段或偏好"}

    graph = StateGraph(State)
    for name, fn in (("clarify", clarify), ("research_plan", research_plan), ("research", research),
                     ("gather", gather), ("propose", propose), ("validate", validate),
                     ("review", review), ("fail", fail)):
        graph.add_node(name, fn)
    graph.add_edge(START, "clarify")
    graph.add_conditional_edges("clarify", lambda s: END if s["status"] == "rejected" else "research_plan")
    graph.add_conditional_edges("research_plan", fan_out, ["research"])
    graph.add_edge("research", "gather")
    graph.add_edge("gather", "propose")
    graph.add_edge("propose", "validate")
    graph.add_conditional_edges("validate", after_validate)
    graph.add_conditional_edges("review", lambda s: "clarify" if s["status"] == "running" else END)
    graph.add_edge("fail", END)
    return graph.compile(checkpointer=checkpointer)
