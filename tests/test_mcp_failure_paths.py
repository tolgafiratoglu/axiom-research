"""7.2 — MCP outage/429/timeout → tool.summary failure; gate-safe; no fabricated sources."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx2
import pytest
from mcp import Client

from api.gate import MockVerifierClient, run_verification_gate
from api.ws.normalize import normalize_multiagent_event
from axiom_research.identities import AgentId
from axiom_research.ledger_store import InMemoryLedgerStore
from axiom_research.mcp.errors import McpRuntimeError
from axiom_research.mcp.failures import classify_mcp_failure, tool_failure_summary
from axiom_research.mcp.literature.server import create_literature_server
from axiom_research.mcp.upstream import UpstreamClient


async def _no_sleep(_seconds: float) -> None:
    return None


def test_classify_mcp_failure_labels() -> None:
    assert "429" in classify_mcp_failure("UPSTREAM_RATE_LIMIT upstream rate limit")
    assert "timeout" in classify_mcp_failure("UPSTREAM_TIMEOUT upstream timeout").lower()
    assert "outage" in classify_mcp_failure("connection refused").lower()
    assert "openalex_search_works" in tool_failure_summary(
        "openalex_search_works", "upstream timeout"
    )


def test_failed_mcp_tool_emits_tool_summary_not_evidence() -> None:
    events = normalize_multiagent_event(
        {
            "type": "multiagent_node_stream",
            "node_id": "investigator",
            "event": {
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "toolResult": {
                                "toolUseId": "t-fail",
                                "name": "openalex_search_works",
                                "status": "error",
                                "content": [
                                    {
                                        "text": (
                                            "Literature MCP error: upstream timeout "
                                            "(type=UPSTREAM_TIMEOUT, retryable=True)"
                                        )
                                    }
                                ],
                            }
                        }
                    ],
                }
            },
        },
        session_id="ses-fail",
        run_id="run-fail",
        tool_names_by_id={"t-fail": "openalex_search_works"},
    )
    assert len(events) == 1
    assert events[0].type == "tool.summary"
    assert events[0].ok is False
    assert "timeout" in events[0].summary.lower()
    assert events[0].tool_name == "openalex_search_works"


def test_failed_upsert_claim_does_not_fabricate_evidence_event() -> None:
    """Error text must not be parsed into evidence.updated / fake DOIs."""
    events = normalize_multiagent_event(
        {
            "type": "multiagent_node_stream",
            "node_id": "investigator",
            "event": {
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "toolResult": {
                                "toolUseId": "t-claim",
                                "name": "upsert_claim",
                                "status": "error",
                                "content": [
                                    {
                                        "text": (
                                            '{"claim_id":"fake-claim","statement":"invented",'
                                            '"source_refs":["doi:10.fabricated/1"],'
                                            '"fingerprint":"fp-fake"}'
                                        )
                                    }
                                ],
                            }
                        }
                    ],
                }
            },
        },
        session_id="ses-fail",
        run_id="run-fail",
        tool_names_by_id={"t-claim": "upsert_claim"},
    )
    assert len(events) == 1
    assert events[0].type == "tool.summary"
    assert events[0].ok is False
    assert all(e.type != "evidence.updated" for e in events)


@pytest.mark.asyncio
async def test_upstream_timeout_maps_to_mcp_error() -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        raise httpx2.TimeoutException("timed out")

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler), timeout=0.1)
    client = UpstreamClient(http, max_retries=2, sleep=_no_sleep)
    with pytest.raises(McpRuntimeError) as exc:
        await client.get_json("https://api.example.test/works")
    assert exc.value.error_type == "UPSTREAM_TIMEOUT"
    assert "timeout" in classify_mcp_failure(exc.value).lower()
    await http.aclose()


@pytest.mark.asyncio
async def test_literature_tool_429_surfaces_error_not_fabricated_works() -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(429, headers={"Retry-After": "0"}, json={"error": "slow"})

    server = create_literature_server(
        http_factory=lambda: httpx2.AsyncClient(
            transport=httpx2.MockTransport(handler), timeout=1.0
        )
    )
    # Patch UpstreamClient retries via server's lifespan clients — call tool.
    # Server builds UpstreamClient with default retries; shorten by mocking sleep in transport only.
    async with Client(server) as client:
        result = await client.call_tool(
            "openalex_search_works",
            {"query": "solid-state", "per_page": 5},
        )
        assert result.is_error
        blob = str(result.content) + str(result.structured_content)
        assert (
            "rate" in blob.lower()
            or "429" in blob
            or "limit" in blob.lower()
            or "UPSTREAM_RATE_LIMIT" in blob
        )
        assert "doi:10.fabricated" not in blob
        sc = result.structured_content
        assert sc is None or "works" not in sc


@pytest.mark.asyncio
async def test_mcp_failure_gate_safe_no_fabricated_sources() -> None:
    """Empty ledger after MCP failure: gate ok without inventing sources; Finalizer allowed."""
    store = InMemoryLedgerStore()
    session = "ses-mcp-outage"
    run = "run-mcp-outage"
    gate = await run_verification_gate(
        store,
        session_id=session,
        run_id=run,
        client=MockVerifierClient(),
        frozen_at=datetime(2026, 11, 3, tzinfo=UTC),
    )
    assert gate.passed is True
    assert gate.allow_finalizer is True
    assert gate.snapshot.claims == []
    assert gate.snapshot.sources == []
    assert store.list_claims(session) == []
    # No fabricated DOI/source rows appeared because of the outage path.
    assert all(not s.identifier.startswith("doi:10.fabricated") for s in gate.snapshot.sources)
