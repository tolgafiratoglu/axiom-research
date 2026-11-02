import json
from pathlib import Path

import httpx2
import pytest
from mcp import Client

from axiom_research.mcp.literature.server import create_literature_server

FIXTURES = Path(__file__).parent / "fixtures" / "literature"

EXPECTED_TOOLS = {
    "openalex_search_works",
    "openalex_get_work",
    "crossref_resolve_doi",
    "arxiv_get_preprint",
    "server_info",
}


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _mock_transport() -> httpx2.MockTransport:
    openalex_search = json.loads(_load("openalex_search.json"))
    openalex_work = json.loads(_load("openalex_work.json"))
    crossref = json.loads(_load("crossref_work.json"))
    arxiv_with_journal = _load("arxiv_entry.xml")
    arxiv_only = _load("arxiv_preprint_only.xml")

    def handler(request: httpx2.Request) -> httpx2.Response:
        host = request.url.host
        path = request.url.path
        if host == "api.openalex.org" and path == "/works" and "search" in request.url.params:
            return httpx2.Response(200, json=openalex_search)
        if host == "api.openalex.org" and path.startswith("/works/"):
            return httpx2.Response(200, json=openalex_work)
        if host == "api.crossref.org" and path.startswith("/works/"):
            return httpx2.Response(200, json=crossref)
        if host == "export.arxiv.org" and path == "/api/query":
            id_list = request.url.params.get("id_list", "")
            body = arxiv_only if id_list.startswith("2102.") else arxiv_with_journal
            return httpx2.Response(
                200,
                content=body,
                headers={"content-type": "application/atom+xml"},
            )
        return httpx2.Response(404, json={"error": "unexpected request", "url": str(request.url)})

    return httpx2.MockTransport(handler)


@pytest.mark.asyncio
async def test_literature_tools_listed_with_distinct_purposes() -> None:
    server = create_literature_server(http_factory=lambda: httpx2.AsyncClient(transport=_mock_transport()))
    async with Client(server) as client:
        listed = await client.list_tools()
        by_name = {tool.name: tool for tool in listed.tools}
        assert EXPECTED_TOOLS <= set(by_name)
        assert "OpenAlex" in (by_name["openalex_search_works"].description or "")
        assert "Crossref" in (by_name["crossref_resolve_doi"].description or "")
        assert "arXiv" in (by_name["arxiv_get_preprint"].description or "")
        assert "not" in (by_name["crossref_resolve_doi"].description or "").lower()


@pytest.mark.asyncio
async def test_openalex_search_fixture() -> None:
    server = create_literature_server(http_factory=lambda: httpx2.AsyncClient(transport=_mock_transport()))
    async with Client(server) as client:
        result = await client.call_tool(
            "openalex_search_works",
            {"query": "open access", "per_page": 5},
        )
        assert not result.is_error
        sc = result.structured_content
        assert sc is not None
        assert sc["count"] == 1
        work = sc["works"][0]
        assert work["openalex_id"] == "https://openalex.org/W2741809807"
        assert work["cited_by_count"] == 42
        assert work["referenced_works"]
        assert "abstract" not in work


@pytest.mark.asyncio
async def test_crossref_resolve_doi_fixture() -> None:
    server = create_literature_server(http_factory=lambda: httpx2.AsyncClient(transport=_mock_transport()))
    async with Client(server) as client:
        result = await client.call_tool(
            "crossref_resolve_doi",
            {"doi": "10.7717/peerj.4375"},
        )
        assert not result.is_error
        sc = result.structured_content
        assert sc is not None
        assert sc["doi"] == "10.7717/peerj.4375"
        assert sc["type"] == "journal-article"
        assert sc["published"] == "2018-2-13"
        assert "abstract" not in sc


@pytest.mark.asyncio
async def test_arxiv_later_publication_vs_preprint_only() -> None:
    server = create_literature_server(http_factory=lambda: httpx2.AsyncClient(transport=_mock_transport()))
    async with Client(server) as client:
        later = await client.call_tool("arxiv_get_preprint", {"arxiv_id": "2101.00001"})
        assert not later.is_error
        later_sc = later.structured_content
        assert later_sc is not None
        assert later_sc["is_preprint"] is True
        assert later_sc["later_publication_signal"] is True
        assert later_sc["journal_ref"]
        assert later_sc["doi"]

        only = await client.call_tool("arxiv_get_preprint", {"arxiv_id": "2102.00002"})
        assert not only.is_error
        only_sc = only.structured_content
        assert only_sc is not None
        assert only_sc["is_preprint"] is True
        assert only_sc["later_publication_signal"] is False
        assert only_sc["journal_ref"] is None
