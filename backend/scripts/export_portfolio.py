"""Export a real, public-safe offline graph run for the static portfolio.

PYTHONPATH=backend backend/.venv/bin/python backend/scripts/export_portfolio.py
Only DemoProvider is used: no API keys, private user records or network calls.
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agents.v3.models import TravelBrief
from app.agents.v3.providers import DemoProvider
from app.agents.v3.workflow import build_graph


async def export(output: Path):
    provider = DemoProvider()
    graph = build_graph(InMemorySaver(), lambda *_: provider)
    config = {"configurable": {"thread_id": "public-offline-example"}}
    brief = TravelBrief(city="武汉", date="2026-11-01", budget_max=300,
                        preferences=["人文历史", "城市漫步"], max_pois=3)
    events = []
    started = perf_counter()

    def record(event):
        events.append({**event, "seq": len(events) + 1})

    async def run(value):
        async for part in graph.astream(value, config, stream_mode="custom", version="v2"):
            record(part["data"])

    await run({"brief": brief.model_dump(), "mode": "demo", "provider": "deepseek",
               "status": "running", "results": {}, "generation": 0})
    pending = await graph.aget_state(config)
    assert pending.interrupts[0].value["kind"] == "review"
    record({"type": "interrupt", "node": "review", "message": "记录中的行程等待用户审核"})
    # This approval belongs to the exported fixture, not to any real trip.
    await run(Command(resume={"action": "approve"}))
    state = (await graph.aget_state(config)).values
    assert state["status"] == "completed" and state["validation"]["feasible"]
    record({"type": "complete", "node": "complete", "message": "离线示例已确认完成"})
    result = {key: state[key] for key in
              ("brief", "draft", "pois", "route", "validation", "research_results", "mode", "status")}
    result.update(
        recorded_at=datetime.now(timezone.utc).isoformat(),
        disclosure="真实 LangGraph 的离线固定数据执行记录；仅作回放，不代表实时模型、地图或票价。",
        events=events,
        metrics={"model_calls": 0, "tool_calls": 0,
                 "proposal_attempts": state["proposal_attempts"],
                 "elapsed_seconds": round(perf_counter() - started, 3)},
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "events": len(events),
                      "pois": len(result["pois"]), "status": result["status"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/portfolio-demo.json"))
    asyncio.run(export(parser.parse_args().output))
