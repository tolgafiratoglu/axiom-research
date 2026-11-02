from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

import httpx2
from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from axiom_research.mcp.errors import McpRuntimeError
from axiom_research.mcp.literature.arxiv import ArxivClient
from axiom_research.mcp.literature.crossref import CrossrefClient
from axiom_research.mcp.literature.models import ArxivRecord, CrossrefWork, OpenAlexSearchResult, OpenAlexWorkSummary
from axiom_research.mcp.literature.openalex import OpenAlexClient
from axiom_research.mcp.upstream import DEFAULT_TIMEOUT, UpstreamClient

HttpFactory = Callable[[], httpx2.AsyncClient]

NAME = "axiom-research-mcp-literature"
INSTRUCTIONS = (
    "Bibliographic metadata from OpenAlex (discovery + citations), "
    "Crossref (DOI registry resolve), and arXiv (preprint vs later publication). "
    "Metadata only: no PDF or abstract bulk download, no vector index."
)


@dataclass
class LiteratureContext:
    openalex: OpenAlexClient
    crossref: CrossrefClient
    arxiv: ArxivClient


def create_literature_server(
    *,
    http_factory: HttpFactory | None = None,
    mailto: str | None = None,
) -> MCPServer:
    @asynccontextmanager
    async def lifespan(_server: MCPServer) -> AsyncIterator[LiteratureContext]:
        http = (
            http_factory()
            if http_factory is not None
            else httpx2.AsyncClient(
                timeout=DEFAULT_TIMEOUT,
                headers={"User-Agent": "axiom-research-mcp-literature/0.1"},
            )
        )
        upstream = UpstreamClient(http)
        ctx = LiteratureContext(
            openalex=OpenAlexClient(upstream, mailto=mailto),
            crossref=CrossrefClient(upstream, mailto=mailto),
            arxiv=ArxivClient(upstream),
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
    async def openalex_search_works(
        ctx: Context[LiteratureContext],
        query: Annotated[str, Field(description="Free-text bibliographic search query.")],
        per_page: Annotated[int, Field(description="Result page size (1-25).", ge=1, le=25)] = 5,
    ) -> OpenAlexSearchResult:
        """OpenAlex: discover works, citation relationships, and identifiers.

        Use for search and citation graph. Not the Crossref DOI registry of record.
        Returns metadata only (no abstracts/PDFs).
        """
        try:
            return await _app(ctx).openalex.search_works(query, per_page=per_page)
        except McpRuntimeError as exc:
            raise _tool_error(exc) from exc

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
    async def openalex_get_work(
        ctx: Context[LiteratureContext],
        work_id: Annotated[
            str,
            Field(description="OpenAlex work id (W…) or doi:… / https://openalex.org/W…"),
        ],
    ) -> OpenAlexWorkSummary:
        """OpenAlex: fetch one work with identifiers and citation links.

        Prefer Crossref for authoritative DOI deposit metadata.
        """
        try:
            return await _app(ctx).openalex.get_work(work_id)
        except McpRuntimeError as exc:
            raise _tool_error(exc) from exc

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
    async def crossref_resolve_doi(
        ctx: Context[LiteratureContext],
        doi: Annotated[str, Field(description="DOI, bare or https://doi.org/…")],
    ) -> CrossrefWork:
        """Crossref: resolve a DOI to publisher registry metadata.

        Use for authoritative deposit metadata for a known DOI. Not a discovery search.
        """
        try:
            return await _app(ctx).crossref.resolve_doi(doi)
        except McpRuntimeError as exc:
            raise _tool_error(exc) from exc

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
    async def arxiv_get_preprint(
        ctx: Context[LiteratureContext],
        arxiv_id: Annotated[
            str,
            Field(description="arXiv id, e.g. 2101.00001 or arxiv:2101.00001"),
        ],
    ) -> ArxivRecord:
        """arXiv: preprint metadata and later-publication signals (journal_ref/DOI).

        Always a preprint source. journal_ref/DOI is a later-publication signal,
        not proof of peer review by itself. Prefer Crossref for published DOI records.
        """
        try:
            return await _app(ctx).arxiv.get_preprint(arxiv_id)
        except McpRuntimeError as exc:
            raise _tool_error(exc) from exc

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
    def server_info() -> dict[str, str]:
        """Identity and metadata-only policy of this server."""
        return {
            "name": NAME,
            "transport": "streamable-http",
            "policy": "metadata_only",
            "providers": "openalex,crossref,arxiv",
        }


def _app(ctx: Context[LiteratureContext]) -> LiteratureContext:
    return ctx.request_context.lifespan_context


def _tool_error(exc: McpRuntimeError) -> Exception:
    return Exception(
        f"Literature MCP error: {exc.message} "
        f"(type={exc.error_type}, retryable={exc.retryable})"
    )
