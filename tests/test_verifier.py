"""5.A — Verifier A2A: clean payload, MCP-only tools, no claim mutation (mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from strands import tool

from axiom_research.ledger import EvidenceKind, VerificationVerdict
from axiom_research.verification import (
    VerificationRequest,
    VerificationResult,
    parse_verification_request,
    parse_verification_result,
)
from verifier.agent import (
    VERIFIER_FORBIDDEN_TOOLS,
    assert_verifier_tools_safe,
    build_verifier_agent,
)
from verifier.server import build_a2a_server


@tool(name="openalex_get_work", description="stub MCP")
def _openalex_get_work(work_id: str) -> str:
    return work_id


@tool(name="upsert_claim", description="forbidden ledger write")
def _upsert_claim(payload: dict) -> dict:
    return payload


def test_verification_request_rejects_swarm_opinions_and_transcript() -> None:
    base = {
        "claim_id": "claim-1",
        "claim_revision": 2,
        "claim_fingerprint": "fp-1",
        "statement": "Reported band gap is in range.",
        "source_refs": ["doi:10.example/1"],
        "evidence_kind": EvidenceKind.COMPUTED_PROPERTY.value,
        "criteria": "Confirm identifier resolves and units match.",
    }
    req = parse_verification_request(base)
    assert req.claim_id == "claim-1"

    with pytest.raises(ValueError, match="Swarm opinions|transcript|extra"):
        parse_verification_request({**base, "swarm_transcript": "planner said verified"})

    with pytest.raises(ValueError, match="Swarm opinions|transcript|extra"):
        parse_verification_request({**base, "agent_opinions": {"investigator": "looks good"}})

    with pytest.raises(ValueError, match="Swarm opinions|transcript|extra"):
        parse_verification_request({**base, "prior_verdicts": ["verified"]})


def test_verification_result_only_allows_verdict_enum() -> None:
    result = parse_verification_result(
        {
            "claim_id": "claim-1",
            "claim_fingerprint": "fp-1",
            "claim_revision": 2,
            "status": "insufficient_evidence",
            "source_refs": ["doi:10.example/1"],
            "verified_revision": 2,
        }
    )
    assert result.status is VerificationVerdict.INSUFFICIENT_EVIDENCE

    with pytest.raises(Exception):
        VerificationResult.model_validate(
            {
                "claim_id": "claim-1",
                "claim_fingerprint": "fp-1",
                "claim_revision": 2,
                "status": "probably_true",
                "source_refs": ["doi:10.example/1"],
                "verified_revision": 2,
            }
        )


def test_verifier_cannot_receive_claim_mutating_tools() -> None:
    assert "upsert_claim" in VERIFIER_FORBIDDEN_TOOLS
    with pytest.raises(RuntimeError, match="claim-mutating"):
        assert_verifier_tools_safe([_upsert_claim])
    with pytest.raises(RuntimeError, match="claim-mutating"):
        build_verifier_agent(
            "ctx-1",
            mcp_tools=[_openalex_get_work, _upsert_claim],
            model=MagicMock(),
        )


def test_build_verifier_agent_mcp_only_no_claim_tools() -> None:
    model = MagicMock(name="model")
    agent = build_verifier_agent("ctx-isolated", mcp_tools=[_openalex_get_work], model=model)
    assert agent.name == "verifier"
    names = set(agent.tool_names)
    assert "openalex_get_work" in names
    assert names.isdisjoint(VERIFIER_FORBIDDEN_TOOLS)
    assert "upsert_claim" not in names


def test_a2a_server_uses_agent_factory_not_shared_swarm_agent() -> None:
    model = MagicMock(name="model")
    captured: dict[str, object] = {}

    class FakeA2AServer:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.host = kwargs.get("host")
            self.port = kwargs.get("port")

    with patch("strands.multiagent.a2a.A2AServer", FakeA2AServer):
        server = build_a2a_server(
            mcp_tools=[_openalex_get_work],
            model=model,
            host="127.0.0.1",
            port=9000,
        )
    assert server.port == 9000
    assert "agent_factory" in captured
    assert captured.get("agent") is None
    factory = captured["agent_factory"]
    assert callable(factory)
    agent_a = factory("context-a")
    agent_b = factory("context-b")
    assert agent_a is not agent_b
    assert agent_a.name == "verifier"
