from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Any

import httpx2
from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from axiom_research.mcp.errors import McpRuntimeError
from axiom_research.mcp.research_data.datacite import DataCiteClient
from axiom_research.mcp.research_data.zenodo import ZenodoClient
from axiom_research.mcp.upstream import DEFAULT_TIMEOUT, UpstreamClient
from axiom_research.untrusted import prepare_tool_result

HttpFactory = Callable[[], httpx2.AsyncClient]

NAME = "axiom-research-mcp-research-data"
INSTRUCTIONS = (
    "Deposited research records (Zenodo) and independent PID resolve (DataCite). "
    "Metadata only: no bulk file harvest, no vector index. "
    "Verifier should prefer DataCite for PID checks when Investigator used Zenodo."
)


@dataclass
class ResearchDataContext:
    zenodo: ZenodoClient
    datacite: DataCiteClient


def create_research_data_server(
    *,
    http_factory: HttpFactory | None = None,
) -> MCPServer:
    @asynccontextmanager
    async def lifespan(_server: MCPServer) -> AsyncIterator[ResearchDataContext]:
        http = (
            http_factory()
            if http_factory is not None
            else httpx2.AsyncClient(
                timeout=DEFAULT_TIMEOUT,
                headers={"User-Agent": "axiom-research-mcp-research-data/0.1"},
            )
        )
        upstream = UpstreamClient(http)
        ctx = ResearchDataContext(
            zenodo=ZenodoClient(upstream),
            datacite=DataCiteClient(upstream),
        )
        try:
            yield ctx
        finally:
            await http.aclose()

    mcp = MCPServer(NAME, instructions=INSTRUCTIONS, version="0.1.0", lifespan=lifespan)
    _register_tools(mcp)
    return mcp


def _register_tools(mcp: MCPServer) -> None:
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
    async def zenodo_get_record(
        ctx: Context[ResearchDataContext],
        record_id: Annotated[
            str,
            Field(description="Zenodo record id or 10.5281/zenodo.… DOI"),
        ],
    ) -> dict[str, Any]:
        """Zenodo: deposited record metadata (version, license, concept id).

        Deposit-site metadata. Does not download files. For independent PID
        resolve use datacite_resolve_doi (Verifier path).
        """
        try:
            return prepare_tool_result(await _app(ctx).zenodo.get_record(record_id))
        except McpRuntimeError as exc:
            raise _tool_error(exc) from exc

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
    async def zenodo_search_records(
        ctx: Context[ResearchDataContext],
        query: Annotated[str, Field(description="Zenodo search query")],
        size: Annotated[int, Field(description="Page size (1-25).", ge=1, le=25)] = 5,
    ) -> dict[str, Any]:
        """Zenodo: search deposited records. Metadata only; no file harvest."""
        try:
            return prepare_tool_result(
                await _app(ctx).zenodo.search_records(query, size=size)
            )
        except McpRuntimeError as exc:
            raise _tool_error(exc) from exc

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
    async def datacite_resolve_doi(
        ctx: Context[ResearchDataContext],
        doi: Annotated[str, Field(description="Dataset or other DOI to resolve")],
    ) -> dict[str, Any]:
        """DataCite: independently resolve a PID and its registered metadata.

        Verifier path for dataset DOIs. Not the Zenodo deposit API — use this
        to re-check a DOI Investigator found via Zenodo without sharing Swarm context.
        """
        try:
            return prepare_tool_result(await _app(ctx).datacite.resolve_doi(doi))
        except McpRuntimeError as exc:
            raise _tool_error(exc) from exc

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
    def server_info() -> dict[str, str]:
        """Identity and metadata-only policy of this server."""
        return {
            "name": NAME,
            "transport": "streamable-http",
            "policy": "metadata_only_no_file_harvest",
            "providers": "zenodo,datacite",
            "verifier_hint": "prefer datacite_resolve_doi for independent PID checks",
        }


def _app(ctx: Context[ResearchDataContext]) -> ResearchDataContext:
    return ctx.request_context.lifespan_context


def _tool_error(exc: McpRuntimeError) -> Exception:
    from mcp.server.mcpserver.exceptions import ToolError

    return ToolError(
        f"Research-data MCP error: {exc.message} "
        f"(type={exc.error_type}, retryable={exc.retryable})"
    )
