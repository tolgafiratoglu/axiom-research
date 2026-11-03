"""7.4 — Provider keys only via secrets mount; not in images; no product auth."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from starlette.testclient import TestClient as StarletteTestClient

from api.main import create_app
from axiom_research.mcp.ratelimit import RateLimiter
from axiom_research.mcp.runner import build_asgi_app, build_server
from axiom_research.mcp.servers.literature import NAME as LITERATURE
from axiom_research.settings import (
    PROVIDER_SECRET_NAMES,
    Settings,
    load_gemini_api_key,
    load_mp_api_key,
)

ROOT = Path(__file__).resolve().parents[1]


def test_provider_secrets_are_not_settings_env_fields() -> None:
    fields = set(Settings.model_fields)
    assert "gemini_api_key" not in fields
    assert "mp_api_key" not in fields
    assert "GEMINI_API_KEY" not in fields
    assert "MP_API_KEY" not in fields


def test_mp_and_gemini_keys_ignore_process_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MP_API_KEY", "process-mp-should-be-ignored")
    monkeypatch.setenv("GEMINI_API_KEY", "process-gemini-should-be-ignored")
    secrets = tmp_path / "secrets.env"
    secrets.write_text(
        "MP_API_KEY=from-secrets-mp\nGEMINI_API_KEY=from-secrets-gemini\n",
        encoding="utf-8",
    )
    assert load_mp_api_key(str(secrets)) == "from-secrets-mp"
    assert load_gemini_api_key(str(secrets)) == "from-secrets-gemini"

    empty = tmp_path / "empty.env"
    empty.write_text("# no keys\n", encoding="utf-8")
    assert load_mp_api_key(str(empty)) == ""
    assert load_gemini_api_key(str(empty)) == ""

    cfg = Settings(secrets_env_path=str(secrets))
    assert cfg.mp_api_key == "from-secrets-mp"
    assert cfg.gemini_api_key == "from-secrets-gemini"


def test_compose_does_not_inject_provider_keys_into_environment() -> None:
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for name in PROVIDER_SECRET_NAMES:
        assert f"{name}=" not in text
        assert f"- {name}" not in text
    assert "SECRETS_ENV_PATH=/config/rag/.env" in text
    assert "${HOME}/.config/rag:/config/rag:ro" in text


def test_dockerfiles_and_dockerignore_keep_secrets_out_of_images() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert ".env" in dockerignore
    assert ".config/rag" in dockerignore or "rag/.env" in dockerignore

    for rel in ("mcp/Dockerfile", "verifier/Dockerfile", "api/Dockerfile"):
        body = (ROOT / rel).read_text(encoding="utf-8")
        copy_lines = [
            line.strip()
            for line in body.splitlines()
            if line.strip().upper().startswith("COPY ")
        ]
        assert all(".env" not in line for line in copy_lines)
        assert all("GEMINI_API_KEY" not in line for line in copy_lines)
        assert all("MP_API_KEY" not in line for line in copy_lines)
        assert "compose secrets" in body.lower()


def test_api_and_mcp_health_require_no_product_auth() -> None:
    api = TestClient(create_app())
    live = api.get("/health/live")
    assert live.status_code == 200
    # No Authorization / API key headers required.
    assert "www-authenticate" not in {k.lower() for k in live.headers.keys()}

    mcp_app = build_asgi_app(
        build_server(name=LITERATURE, instructions="test"),
        limiter=RateLimiter(max_requests=30),
    )
    mcp = StarletteTestClient(mcp_app)
    health = mcp.get("/health")
    assert health.status_code == 200
    assert "www-authenticate" not in {k.lower() for k in health.headers.keys()}
