"""AxiomResearch FastAPI entry — WebSocket gateway (no REST chat channel)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from api.health import HealthDeps, liveness_payload, readiness_payload
from api.ws.hub import SessionHub
from api.ws.session import router as ws_router
from axiom_research.settings import Settings, settings


def create_app(
    *,
    hub: SessionHub | None = None,
    cfg: Settings | None = None,
    health_deps: HealthDeps | None = None,
) -> FastAPI:
    app = FastAPI(title="AxiomResearch", version="0.1.0")
    app.state.hub = hub or SessionHub()
    app.state.settings = cfg or settings
    app.state.health_deps = health_deps
    app.include_router(ws_router)

    @app.get("/health")
    @app.get("/health/live")
    def health_live() -> dict[str, Any]:
        """Liveness: process is up. No Postgres/MCP/Gemini checks."""
        return liveness_payload()

    @app.get("/health/ready")
    def health_ready(request: Request) -> Response:
        """Readiness: Postgres + MCP /health. Gemini is never a blocker."""
        deps = getattr(request.app.state, "health_deps", None)
        body, status = readiness_payload(
            request.app.state.settings,
            deps=deps,
        )
        return JSONResponse(body, status_code=status)

    return app


app = create_app()
