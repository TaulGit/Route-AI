"""Single-process durable runner. SSE is a view of the persisted event log.

Browser disconnection does not cancel a run. On process restart, unfinished
threads resume from their last checkpoint. Read-only tool calls in an unfinished
node may repeat; this is at-least-once execution, not exactly-once delivery.
"""

import asyncio
import json
import logging
import time
import uuid
from contextlib import AsyncExitStack
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from .models import ResumeRequest, RunRequest
from .workflow import build_graph, required_fields

logger = logging.getLogger(__name__)


class RunNotFound(Exception):
    pass


class RunConflict(Exception):
    pass


def default_provider(mode, provider):
    from .providers import DemoProvider, LiveProvider
    return DemoProvider() if mode == "demo" else LiveProvider(provider)


class AgentRuntime:
    def __init__(self, path: str, provider_factory=default_provider, *, allow_live=True):
        self.path = path
        self.provider_factory = provider_factory
        self.allow_live = allow_live
        self.jobs = {}
        self.write_lock = asyncio.Lock()
        self.stack = AsyncExitStack()

    async def open(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = await self.stack.enter_async_context(aiosqlite.connect(self.path))
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, request TEXT NOT NULL,
                status TEXT NOT NULL, interrupt_id TEXT, started REAL NOT NULL,
                elapsed REAL NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS agent_events (
                run_id TEXT NOT NULL, seq INTEGER NOT NULL, body TEXT NOT NULL,
                PRIMARY KEY (run_id, seq)
            );
        """)
        await self.db.commit()
        saver = await self.stack.enter_async_context(AsyncSqliteSaver.from_conn_string(self.path))
        await saver.setup()
        self.graph = build_graph(saver, self.provider_factory)
        cursor = await self.db.execute("SELECT id,request FROM agent_runs WHERE status='running'")
        for row in await cursor.fetchall():
            if not self.allow_live and json.loads(row["request"])["mode"] == "live":
                message = "演示服务器不恢复实时任务；请在实时服务中重新发起"
                await self._emit(row["id"], {"type": "error", "message": message})
                await self._update(row["id"], "failed", message=message)
                continue
            self._launch(row["id"], None)
        return self

    async def close(self):
        jobs = list(self.jobs.values())
        for task in jobs:
            task.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
        await self.stack.aclose()

    @staticmethod
    def config(run_id):
        return {"configurable": {"thread_id": run_id}, "recursion_limit": 80}

    async def _row(self, run_id, owner=None):
        cursor = await self.db.execute("SELECT * FROM agent_runs WHERE id=?", (run_id,))
        row = await cursor.fetchone()
        if row is None or (owner is not None and row["owner"] != owner):
            raise RunNotFound()
        return dict(row)

    async def events(self, run_id, after=0):
        cursor = await self.db.execute(
            "SELECT body FROM agent_events WHERE run_id=? AND seq>? ORDER BY seq", (run_id, after))
        return [json.loads(r["body"]) for r in await cursor.fetchall()]

    async def _emit(self, run_id, event):
        async with self.write_lock:
            cursor = await self.db.execute(
                "SELECT COALESCE(MAX(seq),0)+1 AS seq FROM agent_events WHERE run_id=?", (run_id,))
            seq = (await cursor.fetchone())["seq"]
            event = {**event, "run_id": run_id, "seq": seq}
            await self.db.execute("INSERT INTO agent_events VALUES (?,?,?)",
                                  (run_id, seq, json.dumps(event, ensure_ascii=False)))
            await self.db.commit()

    async def _update(self, run_id, status, interrupt_id=None, message="", elapsed=0):
        async with self.write_lock:
            await self.db.execute(
                "UPDATE agent_runs SET status=?,interrupt_id=?,message=?,elapsed=elapsed+? WHERE id=?",
                (status, interrupt_id, message, elapsed, run_id))
            await self.db.commit()

    async def create(self, request: RunRequest, owner: str):
        if request.mode == "live" and not self.allow_live:
            raise ValueError("演示服务器禁止实时调用")
        if request.mode == "demo" and request.brief.city not in ("", "武汉"):
            raise ValueError("离线示例仅提供武汉数据，请切换实时模式查询其他城市")
        run_id = str(uuid.uuid4())
        async with self.write_lock:
            await self.db.execute("INSERT INTO agent_runs(id,owner,request,status,started) VALUES (?,?,?,?,?)",
                                  (run_id, owner, request.model_dump_json(), "running", time.time()))
            await self.db.commit()
        self._launch(run_id, {"brief": request.brief.model_dump(), "mode": request.mode,
                              "provider": request.provider, "status": "running", "results": {},
                              "generation": 0, "planning_model_calls": 0, "route_calls": 0})
        return run_id

    def _launch(self, run_id, value):
        task = asyncio.create_task(self._drive(run_id, value))
        self.jobs[run_id] = task
        def forget(done):
            if self.jobs.get(run_id) is done:
                self.jobs.pop(run_id, None)
        task.add_done_callback(forget)

    async def _drive(self, run_id, value):
        start = time.perf_counter()
        try:
            if value is None:
                checkpoint = await self.graph.aget_state(self.config(run_id))
                if not checkpoint.values:
                    row = await self._row(run_id)
                    req = RunRequest.model_validate_json(row["request"])
                    value = {"brief": req.brief.model_dump(), "mode": req.mode,
                             "provider": req.provider, "status": "running", "results": {}}
                elif checkpoint.interrupts:
                    # A crash between claiming a resume and writing its checkpoint
                    # must not manufacture an answer. Re-expose the pending question.
                    await self._finish(run_id, start)
                    return
                elif not checkpoint.next:
                    await self._finish(run_id, start)
                    return
            async for event in self.graph.astream(value, self.config(run_id),
                                                  stream_mode="custom", version="v2", durability="sync"):
                await self._emit(run_id, event["data"])
            await self._finish(run_id, start)
        except asyncio.CancelledError:
            # Leave the thread running so the next process can recover it.
            raise
        except Exception as exc:
            logger.exception("Agent run %s failed", run_id)
            message = f"规划执行失败 ({type(exc).__name__})，请检查服务日志后重新发起"
            await self._emit(run_id, {"type": "error", "message": message})
            await self._update(run_id, "failed", message=message, elapsed=time.perf_counter() - start)

    async def _finish(self, run_id, start):
        state = await self.graph.aget_state(self.config(run_id))
        elapsed = time.perf_counter() - start
        if state.interrupts:
            pending = state.interrupts[0]
            await self._emit(run_id, {"type": "interrupt", "message": "等待补充信息或审核",
                                      "data": {"id": pending.id, "payload": pending.value}})
            await self._update(run_id, "interrupted", pending.id, elapsed=elapsed)
        else:
            status = state.values.get("status", "failed")
            if status not in ("completed", "failed", "rejected"):
                status = "failed"
            # Write the terminal event before status, so a stream cannot miss its last event.
            snapshot = await self.snapshot(run_id)
            snapshot.update(status=status, message=state.values.get("message", ""))
            snapshot["metrics"]["elapsed_seconds"] += round(elapsed, 3)
            await self._emit(run_id, {"type": "complete", "data": snapshot})
            await self._update(run_id, status, message=state.values.get("message", ""), elapsed=elapsed)

    async def resume(self, run_id, owner, request: ResumeRequest):
        row = await self._row(run_id, owner)
        if json.loads(row["request"])["mode"] == "live" and not self.allow_live:
            raise ValueError("演示服务器禁止恢复实时任务")
        state = await self.graph.aget_state(self.config(run_id))
        if not state.interrupts or state.interrupts[0].id != request.interrupt_id:
            raise RunConflict("审核已更新，请刷新后重试")
        pending = state.interrupts[0].value
        allowed = {"clarify", "reject"} if pending["kind"] == "clarify" else {"approve", "revise", "reject"}
        if request.action not in allowed:
            raise ValueError("当前阶段不支持该操作")
        if request.action in ("clarify", "revise"):
            if request.brief is None or required_fields(request.brief):
                raise ValueError("请完整提供城市、日期和预算")
            if state.values["mode"] == "demo" and request.brief.city != "武汉":
                raise ValueError("离线示例仅支持武汉")
        async with self.write_lock:
            cursor = await self.db.execute(
                "UPDATE agent_runs SET status='running',interrupt_id=NULL WHERE id=? AND owner=? "
                "AND status='interrupted' AND interrupt_id=?", (run_id, owner, request.interrupt_id))
            await self.db.commit()
            if cursor.rowcount != 1:
                raise RunConflict("会话正在运行或审核已提交")
        self._launch(run_id, Command(resume=request.model_dump(exclude_none=True)))

    async def snapshot(self, run_id, owner=None):
        row = await self._row(run_id, owner)
        state = await self.graph.aget_state(self.config(run_id))
        values = state.values or {}
        request = json.loads(row["request"])
        output = {"run_id": run_id, "status": row["status"], "mode": request["mode"],
                  "brief": values.get("brief", request["brief"]), "message": row["message"],
                  **{key: values.get(key) for key in ("draft", "validation", "research_results", "pois", "route")},
                  "metrics": {"tool_calls": sum(r["tool_calls"] for r in values.get("results", {}).values()) + values.get("route_calls", 0),
                              "model_calls": sum(r["model_calls"] for r in values.get("results", {}).values()) + values.get("planning_model_calls", 0),
                              "proposal_attempts": values.get("proposal_attempts", 0),
                              "elapsed_seconds": round(row["elapsed"], 3)},
                  "events": await self.events(run_id)}
        if state.interrupts:
            pending = state.interrupts[0]
            output["interrupt"] = {"id": pending.id, "payload": pending.value}
        return output

    async def stream(self, run_id):
        last = 0
        while True:
            for event in await self.events(run_id, last):
                last = event["seq"]
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
            row = await self._row(run_id)
            if row["status"] != "running":
                # Read once more to cover the event/status write boundary.
                for event in await self.events(run_id, last):
                    last = event["seq"]
                    yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                return
            await asyncio.sleep(0.1)
