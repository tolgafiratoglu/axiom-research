"""Shared Streamable HTTP MCP runner used by all three scientific servers."""

from __future__ import annotations

import os

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from axiom_research.mcp.ratelimit import RateLimitMiddleware, RateLimiter


def build_server(*, name: str, instructions: str) -> MCPServer:
    mcp = MCPServer(
        name,
        instructions=instructions,
        version="0.1.0",
    )

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
    def server_info() -> dict[str, str]:
        """Identity and metadata-only policy of this server. Not a scientific data tool."""
        return {
            "name": name,
            "transport": "streamable-http",
            "policy": "metadata_only",
        }

    return mcp


def build_asgi_app(
    server: MCPServer,
    *,
    limiter: RateLimiter | None = None,
) -> Starlette:
    """Compose health + Streamable HTTP. No product auth (localhost Compose)."""
    inner = server.streamable_http_app(json_response=True, stateless_http=True)

    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "server": server.name})

    app = Starlette(
        routes=[
            Route("/health", health),
            Mount("/", app=inner),
        ],
    )
    return RateLimitMiddleware(app, limiter=limiter or RateLimiter())  # type: ignore[return-value]


def run_server(*, name: str, instructions: str, host: str = "0.0.0.0", port: int = 8080) -> None:
    server = build_server(name=name, instructions=instructions)
    app = build_asgi_app(server)
    import uvicorn

    uvicorn.run(app, host=host, port=port)


def port_from_env(default: int = 8080) -> int:
    raw = os.environ.get("PORT", str(default))
    return int(raw)
