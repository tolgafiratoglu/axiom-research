import json
from pathlib import Path

import httpx2
import pytest
from mcp import Client

from axiom_research.mcp.research_data.server import create_research_data_server

FIXTURES = Path(__file__).parent / "fixtures" / "research_data"

EXPECTED_TOOLS = {
    "zenodo_get_record",
    "zenodo_search_records",
    "datacite_resolve_doi",
    "server_info",
}


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _mock_transport() -> httpx2.MockTransport:
    zenodo_record = _load_json("zenodo_record.json")
    zenodo_search = _load_json("zenodo_search.json")
    datacite = _load_json("datacite_doi.json")

    def handler(request: httpx2.Request) -> httpx2.Response:
        host = request.url.host
        path = request.url.path
        if host == "zenodo.org" and path == "/api/records":
            return httpx2.Response(200, json=zenodo_search)
        if host == "zenodo.org" and path.startswith("/api/records/"):
            return httpx2.Response(200, json=zenodo_record)
        if host == "api.datacite.org" and path.startswith("/dois/"):
            return httpx2.Response(200, json=datacite)
        return httpx2.Response(404, json={"error": "unexpected", "url": str(request.url)})

    return httpx2.MockTransport(handler)


def _server() -> object:
    return create_research_data_server(
        http_factory=lambda: httpx2.AsyncClient(transport=_mock_transport()),
    )


@pytest.mark.asyncio
async def test_research_data_tools_distinct_purposes() -> None:
    async with Client(_server()) as client:
        listed = await client.list_tools()
        by_name = {tool.name: tool for tool in listed.tools}
        assert EXPECTED_TOOLS <= set(by_name)
        zenodo_desc = by_name["zenodo_get_record"].description or ""
        datacite_desc = by_name["datacite_resolve_doi"].description or ""
        assert "Zenodo" in zenodo_desc
        assert "DataCite" in datacite_desc
        assert "Verifier" in datacite_desc or "independent" in datacite_desc.lower()
        assert "not" in zenodo_desc.lower() or "DataCite" in zenodo_desc


@pytest.mark.asyncio
async def test_zenodo_get_record_fixture() -> None:
    async with Client(_server()) as client:
        result = await client.call_tool("zenodo_get_record", {"record_id": "1234567"})
        assert not result.is_error
        sc = result.structured_content
        assert sc is not None
        assert sc["record_id"] == "1234567"
        assert sc["version"] == "1.1.0"
        assert sc["license_id"] == "cc-by-4.0"
        assert sc["files_count"] == 2
        assert "files" not in sc
        assert sc["evidence_kind"] == "dataset"


@pytest.mark.asyncio
async def test_zenodo_search_fixture() -> None:
    async with Client(_server()) as client:
        result = await client.call_tool(
            "zenodo_search_records",
            {"query": "solid-state battery", "size": 5},
        )
        assert not result.is_error
        sc = result.structured_content
        assert sc is not None
        assert sc["count"] == 1
        assert sc["records"][0]["doi"] == "10.5281/zenodo.1234567"


@pytest.mark.asyncio
async def test_datacite_resolve_doi_fixture() -> None:
    async with Client(_server()) as client:
        result = await client.call_tool(
            "datacite_resolve_doi",
            {"doi": "10.5281/zenodo.1234567"},
        )
        assert not result.is_error
        sc = result.structured_content
        assert sc is not None
        assert sc["doi"] == "10.5281/zenodo.1234567"
        assert sc["resource_type_general"] == "Dataset"
        assert sc["evidence_kind"] == "dataset_pid"
        assert sc["client_id"] == "cern.zenodo"
