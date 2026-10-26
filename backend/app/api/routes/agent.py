"""Durable v3 API. Every persisted run is scoped to its authenticated owner."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ...agents.v3.models import ResumeRequest, RunRequest
from ...agents.v3.runtime import RunConflict, RunNotFound
from ...core.config import get_settings
from ...core.supabase_auth import get_current_user

router = APIRouter(prefix="/agent", tags=["RouteAI Agent v3"])


async def owner(request: Request):
    if get_settings().routeai_demo:
        return "local-demo"
    return (await get_current_user(request)).id


def stream(runtime, run_id):
    return StreamingResponse(runtime.stream(run_id), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/runs")
async def create_run(body: RunRequest, request: Request, user=Depends(owner)):
    # An explicit demo server can never accidentally spend a configured API key.
    if get_settings().routeai_demo and body.mode != "demo":
        raise HTTPException(400, "本地演示服务器仅接受 demo 模式；实时模式请关闭 ROUTEAI_DEMO 并登录")
    runtime = request.app.state.agent_runtime
    try:
        run_id = await runtime.create(body, user)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return stream(runtime, run_id)


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request, user=Depends(owner)):
    try:
        return await request.app.state.agent_runtime.snapshot(run_id, user)
    except RunNotFound as exc:
        raise HTTPException(404, "会话不存在") from exc


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str, body: ResumeRequest, request: Request, user=Depends(owner)):
    runtime = request.app.state.agent_runtime
    try:
        await runtime.resume(run_id, user, body)
    except RunNotFound as exc:
        raise HTTPException(404, "会话不存在") from exc
    except RunConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return stream(runtime, run_id)
