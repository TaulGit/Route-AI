import asyncio
import json
import os
import sys

import httpx
import pytest

from app.agents.v3.models import ResumeRequest, RunRequest, TravelBrief
from app.agents.v3.providers import DemoProvider
from app.agents.v3.runtime import AgentRuntime, RunConflict, RunNotFound
from app.api.agent_app import create_app
from app.api.routes.agent import owner
from app.core.config import get_settings


def request(**brief):
    return RunRequest(mode="demo", brief=TravelBrief(city="武汉", date="2026-11-01",
                      budget_max=300, **brief))


async def settled(runtime, run_id):
    job = runtime.jobs.get(run_id)
    if job:
        await asyncio.wait_for(asyncio.shield(job), 10)
    return await runtime.snapshot(run_id)


async def test_sqlite_resume_across_restart_and_owner_isolation(tmp_path):
    path = str(tmp_path / "durable.sqlite3")
    first = await AgentRuntime(path).open()
    run_id = await first.create(request(), "alice")
    before = await settled(first, run_id)
    assert before["status"] == "interrupted"
    assert before["interrupt"]["payload"]["kind"] == "review"
    await first.close()
    second = await AgentRuntime(path).open()
    try:
        with pytest.raises(RunNotFound):
            await second.snapshot(run_id, "bob")
        restored = await second.snapshot(run_id, "alice")
        assert restored["draft"] == before["draft"]
        await second.resume(run_id, "alice", ResumeRequest(
            action="approve", interrupt_id=restored["interrupt"]["id"]))
        after = await settled(second, run_id)
        assert after["status"] == "completed"
        assert len([e for e in after["events"] if e.get("node") == "research_plan" and e["type"] == "node_start"]) == 1
        assert [e["seq"] for e in after["events"]] == list(range(1, len(after["events"]) + 1))
    finally:
        await second.close()


async def test_clarify_then_review_stale_and_duplicate_resume(tmp_path):
    runtime = await AgentRuntime(str(tmp_path / "clarify.sqlite3")).open()
    try:
        run_id = await runtime.create(RunRequest(mode="demo", brief=TravelBrief()), "alice")
        empty = await settled(runtime, run_id)
        old_id = empty["interrupt"]["id"]
        assert set(empty["interrupt"]["payload"]["missing"]) == {"city", "date", "budget_max"}
        await runtime.resume(run_id, "alice", ResumeRequest(
            action="clarify", interrupt_id=old_id, brief=request().brief))
        with pytest.raises(RunConflict):
            await runtime.resume(run_id, "alice", ResumeRequest(action="clarify", interrupt_id=old_id, brief=request().brief))
        current = await settled(runtime, run_id)
        with pytest.raises(RunConflict):
            await runtime.resume(run_id, "alice", ResumeRequest(action="approve", interrupt_id=old_id))
        await runtime.resume(run_id, "alice", ResumeRequest(action="reject", interrupt_id=current["interrupt"]["id"]))
        assert (await settled(runtime, run_id))["status"] == "rejected"
    finally:
        await runtime.close()


async def test_process_shutdown_mid_research_recovers_checkpoint(tmp_path):
    started = asyncio.Event()
    class Slow(DemoProvider):
        async def research(self, brief, task):
            started.set()
            await asyncio.Event().wait()
    path = str(tmp_path / "unfinished.sqlite3")
    first = await AgentRuntime(path, lambda *_: Slow()).open()
    run_id = await first.create(request(), "alice")
    await asyncio.wait_for(started.wait(), 5)
    await first.close()
    second = await AgentRuntime(path).open()
    try:
        result = await settled(second, run_id)
        assert result["status"] == "interrupted"
        assert result["validation"]["feasible"]
        assert result["interrupt"]["payload"]["kind"] == "review"
    finally:
        await second.close()


async def test_disconnected_browser_does_not_cancel_job(tmp_path):
    runtime = await AgentRuntime(str(tmp_path / "disconnect.sqlite3")).open()
    try:
        run_id = await runtime.create(request(), "alice")
        stream = runtime.stream(run_id)
        await anext(stream)
        await stream.aclose()
        assert (await settled(runtime, run_id))["status"] == "interrupted"
    finally:
        await runtime.close()


async def test_two_separate_python_processes_resume_same_checkpoint(tmp_path):
    script = '''
import asyncio, json, sys
from app.agents.v3.runtime import AgentRuntime
from app.agents.v3.models import RunRequest, TravelBrief, ResumeRequest
async def main():
    r = await AgentRuntime(sys.argv[1]).open()
    try:
        if len(sys.argv) == 2:
            key = await r.create(RunRequest(mode="demo",brief=TravelBrief(city="武汉",date="2026-11-01",budget_max=300)), "alice")
        else:
            key = sys.argv[2]
            s = await r.snapshot(key, "alice")
            await r.resume(key, "alice", ResumeRequest(action="approve",interrupt_id=s["interrupt"]["id"]))
        job = r.jobs.get(key)
        if job: await job
        s = await r.snapshot(key, "alice")
        print(json.dumps({"run_id":key,"status":s["status"]}))
    finally: await r.close()
asyncio.run(main())
'''
    path = str(tmp_path / "process.sqlite3")
    env = {**os.environ, "PYTHONPATH": "backend"}
    async def launch(*args):
        child = await asyncio.create_subprocess_exec(sys.executable, "-c", script, path, *args,
                    env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(child.communicate(), 15)
        assert child.returncode == 0, stderr.decode()
        return json.loads(stdout)
    first = await launch()
    assert first["status"] == "interrupted"
    second = await launch(first["run_id"])
    assert second == {"run_id": first["run_id"], "status": "completed"}


async def test_demo_api_stream_and_resume_status(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "routeai_demo", True)
    monkeypatch.setattr(get_settings(), "agent_db_path", str(tmp_path / "api.sqlite3"))
    app = create_app()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            response = await client.post("/api/agent/runs", json=request().model_dump())
            assert response.status_code == 200
            events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
            assert events[-1]["type"] == "interrupt"
            run_id = events[0]["run_id"]
            state = (await client.get(f"/api/agent/runs/{run_id}")).json()
            approved = await client.post(f"/api/agent/runs/{run_id}/resume", json={
                "action": "approve", "interrupt_id": state["interrupt"]["id"]})
            assert approved.status_code == 200
            assert (await client.get(f"/api/agent/runs/{run_id}")).json()["status"] == "completed"
            live = request().model_dump()
            live["mode"] = "live"
            assert (await client.post("/api/agent/runs", json=live)).status_code == 400


async def test_api_auth_and_cross_owner_access(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "routeai_demo", False)
    monkeypatch.setattr(get_settings(), "agent_db_path", str(tmp_path / "auth.sqlite3"))
    app = create_app()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            assert (await client.post("/api/agent/runs", json=request().model_dump())).status_code == 401
            app.dependency_overrides[owner] = lambda: "alice"
            response = await client.post("/api/agent/runs", json=request().model_dump())
            events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
            run_id = events[0]["run_id"]
            state = (await client.get(f"/api/agent/runs/{run_id}")).json()
            app.dependency_overrides[owner] = lambda: "bob"
            assert (await client.get(f"/api/agent/runs/{run_id}")).status_code == 404
            assert (await client.post(f"/api/agent/runs/{run_id}/resume", json={
                "action": "approve", "interrupt_id": state["interrupt"]["id"]})).status_code == 404


async def test_error_event_delivered_before_terminal_stream_status(tmp_path):
    class Broken(DemoProvider):
        async def research_plan(self, brief):
            raise RuntimeError("scripted failure")
    runtime = await AgentRuntime(str(tmp_path / "error.sqlite3"), lambda *_: Broken()).open()
    try:
        run_id = await runtime.create(request(), "alice")
        frames = [frame async for frame in runtime.stream(run_id)]
        events = [json.loads(frame[6:]) for frame in frames]
        assert events[-1]["type"] == "error"
        assert (await runtime.snapshot(run_id))["status"] == "failed"
    finally:
        await runtime.close()


async def test_demo_runtime_blocks_old_live_recovery_and_resume(tmp_path):
    started = asyncio.Event()
    class Slow(DemoProvider):
        async def research(self, brief, task):
            started.set()
            await asyncio.Event().wait()
    path = str(tmp_path / "demo_guard.sqlite3")
    first = await AgentRuntime(path, lambda *_: Slow()).open()
    req = request().model_copy(update={"mode": "live"})
    run_id = await first.create(req, "alice")
    await asyncio.wait_for(started.wait(), 5)
    await first.close()
    calls = []
    def forbidden(*args):
        calls.append(args)
        raise AssertionError("Demo recovery must not invoke a live provider")
    second = await AgentRuntime(path, forbidden, allow_live=False).open()
    try:
        result = await second.snapshot(run_id, "alice")
        assert result["status"] == "failed"
        assert calls == []
        with pytest.raises(ValueError, match="禁止实时调用"):
            await second.create(req, "alice")
        with pytest.raises(ValueError, match="禁止恢复实时任务"):
            await second.resume(run_id, "alice", ResumeRequest(action="approve", interrupt_id="stale"))
    finally:
        await second.close()


@pytest.mark.parametrize("changes", [{"start_time": "9:00"}, {"date": "2026-02-30"}, {"end_time": "08:00"}])
def test_invalid_brief_rejected(changes):
    with pytest.raises(ValueError):
        TravelBrief(**changes)
