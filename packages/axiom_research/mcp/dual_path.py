"""Zenodo (Investigator) vs DataCite (Verifier) dual fetch for the same PID (9.3).

Same dataset DOI may appear on both paths; tool allowlists force independent
re-fetch. MCP server still exposes both tools — role filters apply at agent build.
"""

from __future__ import annotations

from typing import Any, Literal

from axiom_research.demo.pins import load_canonical_pins

Role = Literal["investigator", "verifier"]

# Substring markers for research-data dual-path tools.
ZENODO_TOOL_PREFIX = "zenodo_"
DATACITE_TOOL_PREFIX = "datacite_"


def dual_path_dataset_doi() -> str:
    """Pinned PID that must be fetched on both paths (same id, different tools)."""
    return load_canonical_pins().zenodo.doi


def tool_name(tool: Any) -> str | None:
    for attr in ("tool_name", "name", "__name__"):
        value = getattr(tool, attr, None)
        if isinstance(value, str) and value:
            return value
    spec = getattr(tool, "tool_spec", None) or getattr(tool, "spec", None)
    if isinstance(spec, dict) and spec.get("name"):
        return str(spec["name"])
    return None


def is_zenodo_tool(name: str) -> bool:
    return name.startswith(ZENODO_TOOL_PREFIX) or ZENODO_TOOL_PREFIX in name


def is_datacite_tool(name: str) -> bool:
    return name.startswith(DATACITE_TOOL_PREFIX) or DATACITE_TOOL_PREFIX in name


def filter_mcp_tools_for_role(tools: list[Any], role: Role) -> list[Any]:
    """Investigator keeps Zenodo (drops DataCite); Verifier keeps DataCite (drops Zenodo)."""
    out: list[Any] = []
    for tool in tools:
        name = tool_name(tool) or ""
        if role == "investigator" and is_datacite_tool(name):
            continue
        if role == "verifier" and is_zenodo_tool(name):
            continue
        out.append(tool)
    return out


def assert_dual_path_tool_split(investigator_names: set[str], verifier_names: set[str]) -> None:
    """Hard check used by tests / startup: paths must differ for dataset tools."""
    inv_zenodo = {n for n in investigator_names if is_zenodo_tool(n)}
    inv_datacite = {n for n in investigator_names if is_datacite_tool(n)}
    ver_zenodo = {n for n in verifier_names if is_zenodo_tool(n)}
    ver_datacite = {n for n in verifier_names if is_datacite_tool(n)}
    if not inv_zenodo:
        raise RuntimeError("Investigator must retain at least one zenodo_* tool")
    if inv_datacite:
        raise RuntimeError(
            "Investigator must not receive datacite_* tools (Verifier dual path): "
            + ", ".join(sorted(inv_datacite))
        )
    if not ver_datacite:
        raise RuntimeError("Verifier must retain at least one datacite_* tool")
    if ver_zenodo:
        raise RuntimeError(
            "Verifier must not receive zenodo_* tools (Investigator dual path): "
            + ", ".join(sorted(ver_zenodo))
        )
