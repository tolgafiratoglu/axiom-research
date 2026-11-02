import json
from pathlib import Path

import httpx2
import pytest
from mcp import Client

from axiom_research.mcp.materials.server import create_materials_server

FIXTURES = Path(__file__).parent / "fixtures" / "materials"

EXPECTED_TOOLS = {
    "materials_project_get_material",
    "materials_project_search_formula",
    "pubchem_get_compound",
    "server_info",
}


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _mock_transport() -> httpx2.MockTransport:
    mp149 = _load_json("mp_summary_mp149.json")
    lifepo4 = _load_json("mp_summary_lifepo4.json")
    aspirin = _load_json("pubchem_cid_2244.json")

    def handler(request: httpx2.Request) -> httpx2.Response:
        host = request.url.host
        path = request.url.path
        if host == "api.materialsproject.org" and path.startswith("/materials/summary"):
            assert request.headers.get("x-api-key") == "test-mp-key"
            if request.url.params.get("material_ids") == "mp-149":
                return httpx2.Response(200, json=mp149)
            if request.url.params.get("formula") == "LiFePO4":
                return httpx2.Response(200, json=lifepo4)
            return httpx2.Response(200, json={"data": [], "meta": {"total_doc": 0}})
        if host == "pubchem.ncbi.nlm.nih.gov" and "/compound/cid/2244/" in path:
            return httpx2.Response(200, json=aspirin)
        if host == "pubchem.ncbi.nlm.nih.gov" and "/compound/name/Aspirin/" in path:
            return httpx2.Response(200, json=aspirin)
        return httpx2.Response(404, json={"error": "unexpected", "url": str(request.url)})

    return httpx2.MockTransport(handler)


def _server() -> object:
    return create_materials_server(
        http_factory=lambda: httpx2.AsyncClient(transport=_mock_transport()),
        mp_api_key="test-mp-key",
    )


@pytest.mark.asyncio
async def test_materials_tools_listed_distinct_purposes() -> None:
    async with Client(_server()) as client:
        listed = await client.list_tools()
        by_name = {tool.name: tool for tool in listed.tools}
        assert EXPECTED_TOOLS <= set(by_name)
        mp_desc = by_name["materials_project_get_material"].description or ""
        pc_desc = by_name["pubchem_get_compound"].description or ""
        assert "computed" in mp_desc.lower() or "DFT" in mp_desc
        assert "Never experimental" in mp_desc or "experimental" in mp_desc.lower()
        assert "PubChem" in pc_desc
        assert "Not Materials Project" in pc_desc or "not" in pc_desc.lower()


@pytest.mark.asyncio
async def test_materials_project_get_material_computed_only() -> None:
    async with Client(_server()) as client:
        result = await client.call_tool(
            "materials_project_get_material",
            {"material_id": "mp-149"},
        )
        assert not result.is_error
        sc = result.structured_content
        assert sc is not None
        assert sc["material_id"] == "mp-149"
        assert sc["evidence_kind"] == "computed_property"
        assert sc["evidence_kind"] != "measurement"
        assert sc["units"]["band_gap"] == "eV"
        assert any("not experimental" in item.lower() for item in sc["limitations"])


@pytest.mark.asyncio
async def test_materials_project_search_formula_fixture() -> None:
    async with Client(_server()) as client:
        result = await client.call_tool(
            "materials_project_search_formula",
            {"formula": "LiFePO4", "limit": 5},
        )
        assert not result.is_error
        sc = result.structured_content
        assert sc is not None
        assert sc["count"] == 1
        assert sc["materials"][0]["evidence_kind"] == "computed_property"


@pytest.mark.asyncio
async def test_pubchem_get_compound_fixture() -> None:
    async with Client(_server()) as client:
        result = await client.call_tool("pubchem_get_compound", {"cid": 2244})
        assert not result.is_error
        sc = result.structured_content
        assert sc is not None
        assert sc["cid"] == 2244
        assert sc["molecular_formula"] == "C9H8O4"
        assert sc["evidence_kind"] == "compound_metadata"
