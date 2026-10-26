"""Independent workflow acceptance tests using the real LangGraph scheduler."""

import asyncio

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import ValidationError

from app.agents.v3.providers import DemoProvider
from app.agents.v3.workflow import build_graph
from evals.run import FixtureProvider, complete_brief, initial_state, load_cases, run_case


@pytest.mark.asyncio
@pytest.mark.parametrize("case", load_cases(), ids=lambda case: case["id"])
async def test_offline_acceptance_cases(case):
    result = await run_case(case)
    failures = [check for check in result["checks"] if not check["passed"]]
    assert result["passed"], failures


@pytest.mark.asyncio
async def test_send_workers_cross_an_explicit_barrier_before_either_finishes():
    class BarrierProvider(FixtureProvider):
        def __init__(self):
            super().__init__()
            self.arrived = []
            self.released = []
            self.both_arrived = asyncio.Event()

        async def research(self, brief, task):
            self.arrived.append(task.id)
            if len(self.arrived) == 2:
                self.both_arrived.set()
            # Serial execution cannot complete this wait: the graph would have
            # to finish worker 0 before worker 1 ever reaches the barrier.
            await asyncio.wait_for(self.both_arrived.wait(), timeout=2)
            assert len(self.arrived) == 2
            self.released.append(task.id)
            return await super().research(brief, task)

    fixture = BarrierProvider()
    graph = build_graph(InMemorySaver(), lambda *_: fixture)
    result = await graph.ainvoke(initial_state(), {"configurable": {"thread_id": "barrier"}})
    assert set(fixture.arrived) == {"0", "1"}
    assert set(fixture.released) == {"0", "1"}
    assert len(result["research_results"]) == 2
    assert set(result["results"]) == {"1:0", "1:1"}
    assert len(result["pois"]) == 3
    assert result["__interrupt__"][0].value["kind"] == "review"


@pytest.mark.asyncio
async def test_repeated_clarification_does_not_start_research_early():
    fixture = FixtureProvider()
    graph = build_graph(InMemorySaver(), lambda *_: fixture)
    config = {"configurable": {"thread_id": "clarify-twice"}}
    first = await graph.ainvoke(initial_state({}), config)
    assert first["__interrupt__"][0].value["missing"] == ["city", "date", "budget_max"]
    partial = await graph.ainvoke(Command(resume={"brief": {"city": "武汉"}}), config)
    assert partial["__interrupt__"][0].value["missing"] == ["date", "budget_max"]
    assert not fixture.research_calls
    assert fixture.research_plan_calls == 0
    ready = await graph.ainvoke(Command(resume={"brief": complete_brief()}), config)
    assert ready["__interrupt__"][0].value["kind"] == "review"
    assert fixture.research_plan_calls == 1


@pytest.mark.asyncio
async def test_checkpoint_threads_isolate_pending_briefs_and_results():
    graph = build_graph(InMemorySaver(), lambda *_: FixtureProvider())
    config_a = {"configurable": {"thread_id": "trip-a"}}
    config_b = {"configurable": {"thread_id": "trip-b"}}
    await graph.ainvoke(initial_state({}), config_a)
    await graph.ainvoke(initial_state(complete_brief(preferences=["自然"])), config_b)
    snapshot_a = await graph.aget_state(config_a)
    snapshot_b = await graph.aget_state(config_b)
    assert snapshot_a.values["brief"] == {}
    assert not snapshot_a.values.get("pois")
    assert snapshot_b.values["brief"]["preferences"] == ["自然"]
    assert all(poi["id"].startswith("nature-") for poi in snapshot_b.values["pois"])


@pytest.mark.asyncio
async def test_custom_stream_emits_real_node_boundaries_for_parallel_workers():
    fixture = FixtureProvider()
    graph = build_graph(InMemorySaver(), lambda *_: fixture)
    config = {"configurable": {"thread_id": "stream"}}
    events = [event async for event in graph.astream(initial_state(), config, stream_mode="custom")]
    for node in ("research:0", "research:1", "gather", "propose", "validate"):
        starts = [i for i, e in enumerate(events) if e["type"] == "node_start" and e["node"] == node]
        ends = [i for i, e in enumerate(events) if e["type"] == "node_end" and e["node"] == node]
        assert len(starts) == len(ends) == 1
        assert starts[0] < ends[0]
        assert events[ends[0]]["data"]["elapsed_seconds"] >= 0
    assert any(e["type"] == "node_start" and e["node"] == "review" for e in events)
    assert not any(e["type"] == "node_end" and e["node"] == "review" for e in events)


@pytest.mark.asyncio
async def test_invalid_research_plan_schema_surfaces_instead_of_fabricating_tasks():
    class InvalidResearchPlan(FixtureProvider):
        async def research_plan(self, brief):
            return {"tasks": []}

    graph = build_graph(InMemorySaver(), lambda *_: InvalidResearchPlan())
    with pytest.raises(ValidationError):
        await graph.ainvoke(initial_state(), {"configurable": {"thread_id": "bad-plan"}})


@pytest.mark.asyncio
async def test_demo_provider_uses_no_model_or_map_service(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Offline demo attempted a model/map call")

    monkeypatch.setattr("app.agents.v3.providers.get_llm", forbidden)
    monkeypatch.setattr("app.agents.v3.providers.get_amap_service", forbidden)
    graph = build_graph(InMemorySaver(), lambda *_: DemoProvider())
    config = {"configurable": {"thread_id": "real-demo-provider"}}
    result = await graph.ainvoke(initial_state(), config)
    assert result["__interrupt__"][0].value["kind"] == "review"
    assert result["validation"]["feasible"]
    assert all(poi["source"] == "fixture" for poi in result["pois"])
    completed = await graph.ainvoke(Command(resume={"action": "approve"}), config)
    assert completed["status"] == "completed"
