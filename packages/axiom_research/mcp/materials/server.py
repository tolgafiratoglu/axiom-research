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
from axiom_research.mcp.materials.materials_project import MaterialsProjectClient
from axiom_research.mcp.materials.models import (
    MaterialsProjectRecord,
    MaterialsProjectSearchResult,
    PubChemCompound,
)
from axiom_research.mcp.materials.pubchem import PubChemClient
from axiom_research.mcp.upstream import DEFAULT_TIMEOUT, UpstreamClient
from axiom_research.settings import load_mp_api_key, settings

HttpFactory = Callable[[], httpx2.AsyncClient]

NAME = "axiom-research-mcp-materials"
INSTRUCTIONS = (
    "Computed material properties (Materials Project) and compound metadata (PubChem). "
    "Metadata only. Never label computed properties as experimental."
)


@dataclass
class MaterialsContext:
    materials_project: MaterialsProjectClient
    pubchem: PubChemClient


def create_materials_server(
    *,
    http_factory: HttpFactory | None = None,
    mp_api_key: str | None = None,
) -> MCPServer:
    @asynccontextmanager
    async def lifespan(_server: MCPServer) -> AsyncIterator[MaterialsContext]:
        key = mp_api_key if mp_api_key is not None else load_mp_api_key(settings.secrets_env_path)
        if not key:
            raise RuntimeError(
                "MP_API_KEY not set. Add it to "
                f"{settings.secrets_env_path} (not the project .env)."
            )
        http = (
            http_factory()
            if http_factory is not None
            else httpx2.AsyncClient(
                timeout=DEFAULT_TIMEOUT,
                headers={"User-Agent": "axiom-research-mcp-materials/0.1"},
            )
        )
        upstream = UpstreamClient(http, secrets=(key,))
        ctx = MaterialsContext(
            materials_project=MaterialsProjectClient(upstream, api_key=key),
            pubchem=PubChemClient(upstream),
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
    async def materials_project_get_material(
        ctx: Context[MaterialsContext],
        material_id: Annotated[str, Field(description="Materials Project id, e.g. mp-149")],
    ) -> MaterialsProjectRecord:
        """Materials Project: fetch one computed materials summary by material_id.

        Returns DFT-computed properties with units and limitations.
        Never experimental. Not PubChem compound metadata.
        """
        try:
            return await _app(ctx).materials_project.get_material(material_id)
        except McpRuntimeError as exc:
            raise _tool_error(exc) from exc

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
    async def materials_project_search_formula(
        ctx: Context[MaterialsContext],
        formula: Annotated[str, Field(description="Pretty formula, e.g. LiFePO4 or Si")],
        limit: Annotated[int, Field(description="Max rows (1-25).", ge=1, le=25)] = 5,
    ) -> MaterialsProjectSearchResult:
        """Materials Project: search computed summaries by chemical formula.

        Computed properties only (band gap, formation energy, …). Not lab measurements.
        """
        try:
            return await _app(ctx).materials_project.search_by_formula(formula, limit=limit)
        except McpRuntimeError as exc:
            raise _tool_error(exc) from exc

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
    async def pubchem_get_compound(
        ctx: Context[MaterialsContext],
        cid: Annotated[int | None, Field(description="PubChem CID")] = None,
        name: Annotated[str | None, Field(description="Compound name if CID unknown")] = None,
    ) -> PubChemCompound:
        """PubChem PUG REST: compound registry metadata (formula, InChIKey, …).

        Chemical identity metadata. Not Materials Project DFT crystal properties.
        """
        try:
            if cid is not None:
                return await _app(ctx).pubchem.get_by_cid(cid)
            if name and name.strip():
                return await _app(ctx).pubchem.get_by_name(name)
            raise McpRuntimeError("VALIDATION", "provide cid or name")
        except McpRuntimeError as exc:
            raise _tool_error(exc) from exc

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
    def server_info() -> dict[str, str]:
        """Identity and metadata-only policy of this server."""
        return {
            "name": NAME,
            "transport": "streamable-http",
            "policy": "metadata_only",
            "providers": "materials_project,pubchem",
            "computed_vs_experimental": "Materials Project values are computed_property only",
        }


def _app(ctx: Context[MaterialsContext]) -> MaterialsContext:
    return ctx.request_context.lifespan_context


def _tool_error(exc: McpRuntimeError) -> Exception:
    return Exception(
        f"Materials MCP error: {exc.message} "
        f"(type={exc.error_type}, retryable={exc.retryable})"
    )
