"""HTTP MCP clients for Investigator (and later Verifier). No STDIO."""

from __future__ import annotations

from typing import Any

from axiom_research.settings import Settings, settings


def build_mcp_clients(cfg: Settings | None = None) -> list[Any]:
    """Three independent HTTP MCP clients (literature / materials / research-data)."""
    from strands.tools.mcp import MCPClient

    ready = cfg or settings
    return [
        MCPClient(url=ready.mcp_literature_url),
        MCPClient(url=ready.mcp_materials_url),
        MCPClient(url=ready.mcp_research_data_url),
    ]
