"""Live demo bootstrap: MCP tools + A2A Verifier client for SessionHub.

Opt-in via ``AXIOM_LIVE_BOOTSTRAP=1`` so pytest never opens MCP/A2A.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from axiom_research.settings import Settings, settings

logger = logging.getLogger(__name__)


def live_bootstrap_enabled() -> bool:
    return os.environ.get("AXIOM_LIVE_BOOTSTRAP", "").strip() == "1"


@dataclass
class LiveHubDefaults:
    cfg: Settings
    mcp_tools: list[Any] = field(default_factory=list)
    verifier_client: Any | None = None
    mcp_clients: list[Any] = field(default_factory=list)


def load_live_hub_defaults(cfg: Settings | None = None) -> LiveHubDefaults:
    """Start HTTP MCP clients and wire the remote A2A Verifier endpoint."""
    from api.gate.verifier_client import A2AVerifierClient
    from api.swarm.mcp_clients import build_mcp_clients

    ready = cfg or settings
    clients = build_mcp_clients(ready)
    tools: list[Any] = []
    for client in clients:
        client.start()
        tools.extend(client.list_tools_sync())
    verifier = A2AVerifierClient(
        ready.verifier_url,
        timeout=ready.verifier_timeout_seconds,
    )
    logger.info(
        "live bootstrap: %s MCP tools; verifier=%s",
        len(tools),
        ready.verifier_url,
    )
    return LiveHubDefaults(
        cfg=ready,
        mcp_tools=tools,
        verifier_client=verifier,
        mcp_clients=clients,
    )
