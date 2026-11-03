"""A2A Verifier client — application invokes remote Verifier (not Swarm handoff)."""

from __future__ import annotations

import inspect
import json
import re
from typing import Any, Protocol

from axiom_research.ledger import VerificationVerdict
from axiom_research.verification import VerificationRequest, VerificationResult, parse_verification_result


class VerifierUnreachableError(RuntimeError):
    """Transport / timeout failure talking to the Verifier container."""


class VerifierClient(Protocol):
    async def verify(self, request: VerificationRequest) -> VerificationResult: ...


class MockVerifierClient:
    """Deterministic stand-in for unit tests (no live A2A)."""

    def __init__(
        self,
        handler: Any | None = None,
        *,
        unreachable: bool = False,
    ) -> None:
        self._handler = handler
        self._unreachable = unreachable
        self.calls: list[VerificationRequest] = []

    async def verify(self, request: VerificationRequest) -> VerificationResult:
        self.calls.append(request)
        if self._unreachable:
            raise VerifierUnreachableError("verifier unreachable (mock)")
        if self._handler is not None:
            out = self._handler(request)
            if inspect.isawaitable(out):
                out = await out
            return out  # type: ignore[no-any-return]
        return VerificationResult(
            claim_id=request.claim_id,
            claim_fingerprint=request.claim_fingerprint,
            claim_revision=request.claim_revision,
            status=VerificationVerdict.VERIFIED,
            source_refs=list(request.source_refs),
            verified_revision=request.claim_revision,
        )


def _message_text(message: Any) -> str:
    if message is None:
        return ""
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        content = message.get("content") or []
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
        return "\n".join(parts)
    content = getattr(message, "content", None)
    if content is not None:
        return _message_text({"content": content})
    return str(message)


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        raise ValueError("verifier response contained no JSON object")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("verifier JSON was not an object")
    return data


class A2AVerifierClient:
    """Live ``A2AAgent`` wrapper — prompt is the VerificationRequest JSON only."""

    def __init__(self, endpoint: str, *, timeout: float = 60.0) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

    async def verify(self, request: VerificationRequest) -> VerificationResult:
        try:
            from strands.agent.a2a_agent import A2AAgent
        except ImportError as exc:  # pragma: no cover
            raise VerifierUnreachableError("strands A2A client unavailable") from exc

        agent = A2AAgent(endpoint=self.endpoint, timeout=int(self.timeout))
        prompt = request.model_dump_json()
        try:
            result = await agent.invoke_async(prompt)
        except Exception as exc:
            raise VerifierUnreachableError(f"verifier unreachable: {exc}") from exc

        text = _message_text(getattr(result, "message", None))
        try:
            payload = _extract_json_object(text)
            return parse_verification_result(payload)
        except Exception as exc:
            raise ValueError(f"schema-invalid verifier result: {exc}") from exc
