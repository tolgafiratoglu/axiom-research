"""Api liveness / readiness — Postgres + MCP; Gemini is not a readiness blocker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urljoin

import httpx2

from axiom_research.settings import Settings, settings

CheckFn = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class HealthDeps:
    """Injectable checkers for unit tests (no live network/DB)."""

    check_postgres: CheckFn
    check_mcp: Callable[[str, str], dict[str, Any]]


def mcp_health_url(base: str) -> str:
    root = base.rstrip("/") + "/"
    return urljoin(root, "health")


def check_postgres(database_url: str, *, timeout: float = 2.0) -> dict[str, Any]:
    try:
        import psycopg
    except ImportError:
        return {"ok": False, "error": "psycopg not installed"}
    try:
        with psycopg.connect(database_url, connect_timeout=max(1, int(timeout))) as conn:
            conn.execute("SELECT 1")
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 — readiness must never raise
        return {"ok": False, "error": str(exc)[:200]}


def check_mcp_health(name: str, base_url: str, *, timeout: float = 2.0) -> dict[str, Any]:
    url = mcp_health_url(base_url)
    try:
        with httpx2.Client(timeout=timeout) as client:
            response = client.get(url)
        if response.status_code != 200:
            return {
                "ok": False,
                "url": url,
                "error": f"HTTP {response.status_code}",
            }
        return {"ok": True, "url": url}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "url": url, "error": str(exc)[:200]}


def default_deps(cfg: Settings | None = None) -> HealthDeps:
    ready = cfg or settings

    def _pg() -> dict[str, Any]:
        return check_postgres(ready.database_url)

    def _mcp(name: str, base: str) -> dict[str, Any]:
        return check_mcp_health(name, base)

    return HealthDeps(check_postgres=_pg, check_mcp=_mcp)


def liveness_payload() -> dict[str, Any]:
    return {"status": "ok", "role": "api", "probe": "liveness"}


def readiness_payload(
    cfg: Settings | None = None,
    *,
    deps: HealthDeps | None = None,
) -> tuple[dict[str, Any], int]:
    """Postgres + three MCP /health checks. Never calls Gemini."""
    ready_cfg = cfg or settings
    probes = deps or default_deps(ready_cfg)
    checks: dict[str, Any] = {
        "postgres": probes.check_postgres(),
        "mcp_literature": probes.check_mcp(
            "mcp_literature", ready_cfg.mcp_literature_url
        ),
        "mcp_materials": probes.check_mcp(
            "mcp_materials", ready_cfg.mcp_materials_url
        ),
        "mcp_research_data": probes.check_mcp(
            "mcp_research_data", ready_cfg.mcp_research_data_url
        ),
    }
    all_ok = all(bool(item.get("ok")) for item in checks.values())
    body = {
        "status": "ready" if all_ok else "not_ready",
        "probe": "readiness",
        "checks": checks,
        # Explicit: Gemini must not block readiness / Compose start.
        "gemini": {
            "checked": False,
            "readiness_blocker": False,
            "note": "Gemini is not a readiness dependency",
        },
    }
    return body, (200 if all_ok else 503)
