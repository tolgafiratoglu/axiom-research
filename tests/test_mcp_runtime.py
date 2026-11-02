import httpx2
import pytest
from mcp import Client
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.testclient import TestClient

from axiom_research.mcp.errors import McpRuntimeError
from axiom_research.mcp.policy import assert_metadata_only
from axiom_research.mcp.ratelimit import RateLimiter
from axiom_research.mcp.runner import build_asgi_app, build_server
from axiom_research.mcp.servers.literature import NAME as LITERATURE
from axiom_research.mcp.servers.materials import NAME as MATERIALS
from axiom_research.mcp.servers.research_data import NAME as RESEARCH_DATA
from axiom_research.mcp.upstream import UpstreamClient


class WorkMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str


def test_policy_rejects_pdf_and_vector_intent() -> None:
    with pytest.raises(McpRuntimeError, match="POLICY"):
        assert_metadata_only(url="https://example.org/paper.pdf")
    with pytest.raises(McpRuntimeError, match="POLICY"):
        assert_metadata_only(intent="vector_index")
    assert_metadata_only(url="https://api.openalex.org/works/W123")


def test_rate_limiter() -> None:
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    limiter.check("tok", now=1.0)
    limiter.check("tok", now=1.1)
    with pytest.raises(McpRuntimeError, match="RATE_LIMIT"):
        limiter.check("tok", now=1.2)


def test_schema_validation_rejects_untrusted_payload() -> None:
    with pytest.raises(ValidationError):
        WorkMeta.model_validate({"id": 1, "extra": True})


@pytest.mark.asyncio
async def test_upstream_retries_then_maps_429() -> None:
    calls = {"n": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls["n"] += 1
        return httpx2.Response(429, headers={"Retry-After": "0"}, json={"error": "slow"})

    transport = httpx2.MockTransport(handler)
    http = httpx2.AsyncClient(transport=transport, timeout=1.0)
    client = UpstreamClient(http, max_retries=3, sleep=_no_sleep, secrets=("sekrit",))
    with pytest.raises(McpRuntimeError) as exc:
        await client.get_json("https://api.example.test/meta")
    assert exc.value.error_type == "UPSTREAM_RATE_LIMIT"
    assert calls["n"] == 3
    await http.aclose()


@pytest.mark.asyncio
async def test_upstream_blocks_pdf_url() -> None:
    http = httpx2.AsyncClient()
    client = UpstreamClient(http, sleep=_no_sleep)
    with pytest.raises(McpRuntimeError, match="POLICY"):
        await client.get_json("https://example.org/file.pdf")
    await http.aclose()


@pytest.mark.asyncio
async def test_shared_runner_lists_server_info() -> None:
    names = {LITERATURE, MATERIALS, RESEARCH_DATA}
    for name in names:
        server = build_server(name=name, instructions="test")
        async with Client(server) as client:
            listed = await client.list_tools()
            tool_names = {t.name for t in listed.tools}
            assert "server_info" in tool_names
            result = await client.call_tool("server_info", {})
            assert result.structured_content is not None
            assert result.structured_content["name"] == name
            assert result.structured_content["policy"] == "metadata_only"
            assert result.structured_content["transport"] == "streamable-http"


def test_http_health_no_auth() -> None:
    server = build_server(name=LITERATURE, instructions="test")
    app = build_asgi_app(server, limiter=RateLimiter(max_requests=30))
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["server"] == LITERATURE


async def _no_sleep(_seconds: float) -> None:
    return None
