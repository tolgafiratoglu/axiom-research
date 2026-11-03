"""7.3 — api liveness/readiness (Postgres + MCP; Gemini not a blocker)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.health import HealthDeps, mcp_health_url, readiness_payload
from api.main import create_app
from axiom_research.settings import Settings


def _cfg() -> Settings:
    return Settings(
        mcp_literature_url="http://mcp-literature.test",
        mcp_materials_url="http://mcp-materials.test",
        mcp_research_data_url="http://mcp-research-data.test",
        database_url="postgresql://axiom:axiom@postgres:5432/axiom_research",
        gemini_model="gemini-3.6-flash",
    )


def test_mcp_health_url_joins_path() -> None:
    assert mcp_health_url("http://127.0.0.1:8210") == "http://127.0.0.1:8210/health"
    assert mcp_health_url("http://mcp-literature:8080/") == "http://mcp-literature:8080/health"


def test_liveness_ok_without_dependencies() -> None:
    def boom_pg() -> dict:
        raise AssertionError("liveness must not check postgres")

    def boom_mcp(_name: str, _base: str) -> dict:
        raise AssertionError("liveness must not check MCP")

    app = create_app(
        cfg=_cfg(),
        health_deps=HealthDeps(check_postgres=boom_pg, check_mcp=boom_mcp),
    )
    client = TestClient(app)
    for path in ("/health", "/health/live"):
        response = client.get(path)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["probe"] == "liveness"
        assert "gemini" not in body


def test_readiness_ready_when_postgres_and_mcp_ok() -> None:
    seen: list[str] = []

    def pg():
        return {"ok": True}

    def mcp(name: str, base: str):
        seen.append(name)
        return {"ok": True, "url": mcp_health_url(base)}

    app = create_app(
        cfg=_cfg(),
        health_deps=HealthDeps(check_postgres=pg, check_mcp=mcp),
    )
    client = TestClient(app)
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["postgres"]["ok"] is True
    assert body["checks"]["mcp_literature"]["ok"] is True
    assert body["checks"]["mcp_materials"]["ok"] is True
    assert body["checks"]["mcp_research_data"]["ok"] is True
    assert body["gemini"]["checked"] is False
    assert body["gemini"]["readiness_blocker"] is False
    assert set(seen) == {
        "mcp_literature",
        "mcp_materials",
        "mcp_research_data",
    }


def test_readiness_503_when_mcp_down_gemini_still_not_checked() -> None:
    app = create_app(
        cfg=_cfg(),
        health_deps=HealthDeps(
            check_postgres=lambda: {"ok": True},
            check_mcp=lambda name, base: {
                "ok": name != "mcp_materials",
                "url": mcp_health_url(base),
                "error": None if name != "mcp_materials" else "connection refused",
            },
        ),
    )
    client = TestClient(app)
    response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["mcp_materials"]["ok"] is False
    assert body["gemini"]["checked"] is False
    assert body["gemini"]["readiness_blocker"] is False


def test_readiness_payload_ignores_missing_gemini_key() -> None:
    """Even with empty GEMINI credentials path, readiness does not probe Gemini."""
    body, status = readiness_payload(
        _cfg(),
        deps=HealthDeps(
            check_postgres=lambda: {"ok": True},
            check_mcp=lambda name, base: {"ok": True, "url": base},
        ),
    )
    assert status == 200
    assert body["gemini"]["checked"] is False
    assert "api_key" not in body["gemini"]
