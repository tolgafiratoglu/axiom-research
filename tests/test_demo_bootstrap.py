"""Demo finish — live bootstrap opt-in; compose ships real api/web images."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from strands import tool

from api.bootstrap import live_bootstrap_enabled, load_live_hub_defaults
from api.gate import MockVerifierClient
from api.ws.hub import SessionHub
from axiom_research.settings import Settings

ROOT = Path(__file__).resolve().parents[1]


@tool(name="zenodo_get_record", description="stub")
def _zenodo(record_id: str) -> str:
    return record_id


def test_live_bootstrap_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AXIOM_LIVE_BOOTSTRAP", raising=False)
    assert live_bootstrap_enabled() is False


@pytest.mark.asyncio
async def test_start_ask_skips_bootstrap_without_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AXIOM_LIVE_BOOTSTRAP", raising=False)
    hub = SessionHub()

    async def _factory(ctx):
        return
        yield  # pragma: no cover

    hub._run_factory = _factory  # type: ignore[method-assign]
    session = hub.get_or_create("ses-boot-off")
    with patch("api.bootstrap.load_live_hub_defaults") as load:
        await hub.start_ask(session, "hello")
        load.assert_not_called()
    assert session.mcp_tools == []
    assert session.verifier_client is None
    if session.live_task:
        await session.live_task


@pytest.mark.asyncio
async def test_start_ask_applies_live_defaults_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AXIOM_LIVE_BOOTSTRAP", "1")
    hub = SessionHub()

    async def _factory(ctx):
        assert ctx.mcp_tools
        assert ctx.verifier_client is not None
        return
        yield  # pragma: no cover

    hub._run_factory = _factory  # type: ignore[method-assign]
    session = hub.get_or_create("ses-boot-on")
    fake = MagicMock()
    fake.mcp_tools = [_zenodo]
    fake.verifier_client = MockVerifierClient()
    fake.cfg = Settings(gemini_model="gemini-3.6-flash")

    with patch("api.bootstrap.load_live_hub_defaults", return_value=fake):
        run_id = await hub.start_ask(session, "canonical?")
    assert run_id
    assert session.mcp_tools == [_zenodo]
    assert session.verifier_client is fake.verifier_client
    if session.live_task:
        await session.live_task


@pytest.mark.asyncio
async def test_injected_mocks_are_not_overwritten(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AXIOM_LIVE_BOOTSTRAP", "1")
    hub = SessionHub()

    async def _factory(ctx):
        return
        yield  # pragma: no cover

    hub._run_factory = _factory  # type: ignore[method-assign]
    session = hub.get_or_create("ses-boot-mock")
    session.verifier_client = MockVerifierClient()
    session.mcp_tools = [_zenodo]

    with patch("api.bootstrap.load_live_hub_defaults") as load:
        await hub.start_ask(session, "q")
        load.assert_not_called()
    if session.live_task:
        await session.live_task


def test_compose_builds_real_api_and_web() -> None:
    doc = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    api = doc["services"]["api"]
    web = doc["services"]["web"]
    assert api["build"]["dockerfile"] == "api/Dockerfile"
    assert web["build"]["dockerfile"] == "web/Dockerfile"
    assert "busybox" not in str(api.get("image", "")).lower()
    assert "busybox" not in str(web.get("image", "")).lower()
    assert "AXIOM_LIVE_BOOTSTRAP=1" in api["environment"]
    assert (ROOT / "api" / "Dockerfile").is_file()
    assert (ROOT / "web" / "Dockerfile").is_file()


def test_load_live_hub_defaults_wires_verifier_url() -> None:
    cfg = Settings(
        verifier_url="http://verifier:9000",
        mcp_literature_url="http://mcp-literature:8080",
        mcp_materials_url="http://mcp-materials:8080",
        mcp_research_data_url="http://mcp-research-data:8080",
        gemini_model="gemini-3.6-flash",
    )

    class FakeClient:
        def start(self) -> None:
            return None

        def list_tools_sync(self) -> list:
            return [_zenodo]

    with patch("api.swarm.mcp_clients.build_mcp_clients", return_value=[FakeClient()]):
        defaults = load_live_hub_defaults(cfg)
    assert defaults.mcp_tools == [_zenodo]
    assert defaults.verifier_client.endpoint == "http://verifier:9000"
