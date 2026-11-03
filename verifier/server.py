"""Strands A2AServer for the Independent Verifier (own container)."""

from __future__ import annotations

import logging
import os
from typing import Any

from axiom_research.settings import Settings, settings
from verifier.agent import build_verifier_agent

logger = logging.getLogger(__name__)


def _load_mcp_tools(cfg: Settings) -> list[Any]:
    """Independent MCP HTTP clients — not shared with the Swarm process."""
    from api.swarm.mcp_clients import build_mcp_clients

    clients = build_mcp_clients(cfg)
    tools: list[Any] = []
    for client in clients:
        client.start()
        tools.extend(client.list_tools_sync())
    return tools


def build_a2a_server(
    *,
    mcp_tools: list[Any] | None = None,
    model: Any | None = None,
    cfg: Settings | None = None,
    host: str | None = None,
    port: int | None = None,
) -> Any:
    """Construct ``A2AServer`` with ``agent_factory`` (per-context isolation)."""
    from strands.multiagent.a2a import A2AServer

    ready = cfg or settings
    bind_host = host or os.environ.get("VERIFIER_HOST", "0.0.0.0")
    bind_port = port if port is not None else int(os.environ.get("PORT", "9000"))

    # Tools for the card/factory probe; live path loads MCP once at startup.
    shared_tools = list(mcp_tools) if mcp_tools is not None else _load_mcp_tools(ready)

    def agent_factory(context_id: str) -> Any:
        return build_verifier_agent(
            context_id,
            mcp_tools=shared_tools,
            model=model,
            cfg=ready,
        )

    return A2AServer(
        agent_factory=agent_factory,
        host=bind_host,
        port=bind_port,
        http_url=os.environ.get("VERIFIER_HTTP_URL") or f"http://{bind_host}:{bind_port}/",
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    server = build_a2a_server()
    logger.info("Starting Independent Verifier A2A on %s:%s", server.host, server.port)
    server.serve(app_type="fastapi")


if __name__ == "__main__":
    main()
