"""Classify MCP/upstream failures for stable UI ``tool.summary`` events."""

from __future__ import annotations

from axiom_research.mcp.errors import McpRuntimeError


def classify_mcp_failure(text: str | BaseException | None) -> str:
    """Map timeout / 429 / outage text to a short, non-fabricating summary."""
    if isinstance(text, McpRuntimeError):
        raw = f"{text.error_type} {text.message}"
    else:
        raw = str(text or "")
    lowered = raw.lower()
    if "429" in lowered or "rate_limit" in lowered or "rate limit" in lowered:
        return "MCP upstream rate-limited (429)"
    if "timeout" in lowered or "timed out" in lowered:
        return "MCP upstream timeout"
    if (
        "connect" in lowered
        or "unreachable" in lowered
        or "name or service not known" in lowered
        or "connection refused" in lowered
        or "upstream_error" in lowered
        or "upstream error" in lowered
    ):
        return "MCP upstream outage"
    if "not_found" in lowered or "not found" in lowered:
        return "MCP upstream resource not found"
    cleaned = " ".join(raw.split())
    if not cleaned:
        return "MCP tool failed"
    return f"MCP tool failed: {cleaned[:220]}"


def tool_failure_summary(tool_name: str, detail: str | BaseException | None) -> str:
    return f"{tool_name}: {classify_mcp_failure(detail)}"
