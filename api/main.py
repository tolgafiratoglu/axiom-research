"""AxiomResearch FastAPI entry — WebSocket gateway (no REST chat channel)."""

from __future__ import annotations

from fastapi import FastAPI

from api.ws.hub import SessionHub
from api.ws.session import router as ws_router


def create_app(*, hub: SessionHub | None = None) -> FastAPI:
    app = FastAPI(title="AxiomResearch", version="0.1.0")
    app.state.hub = hub or SessionHub()
    app.include_router(ws_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
