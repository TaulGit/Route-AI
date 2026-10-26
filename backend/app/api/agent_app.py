"""Minimal v3 entrypoint; does not import the optional legacy Chroma stack."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..agents.v3.runtime import AgentRuntime
from ..core.config import get_settings
from .routes.agent import router


@asynccontextmanager
async def agent_lifespan(app):
    settings = get_settings()
    runtime = await AgentRuntime(settings.agent_db_path, allow_live=not settings.routeai_demo).open()
    app.state.agent_runtime = runtime
    try:
        yield
    finally:
        await runtime.close()


def create_app():
    app = FastAPI(title="RouteAI Agent", version="3.0.0", lifespan=agent_lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=get_settings().get_cors_origins_list(),
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.include_router(router, prefix="/api")

    @app.get("/health")
    async def health():
        return {"status": "healthy", "version": "3.0.0", "demo": get_settings().routeai_demo}

    return app


app = create_app()
