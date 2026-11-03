"""3.A — Strands GeminiModel wiring + token/cost accounting (mocked, no live Gemini)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from api.swarm.accounting import TokenCostAccounting, usage_from_model_event
from axiom_research.llm.strands_gemini import build_gemini_model
from axiom_research.settings import Settings, require_gemini


def _settings(**overrides: object) -> Settings:
    data: dict[str, object] = {
        "llm_provider": "gemini",
        "gemini_model": "gemini-3.6-flash",
        "secrets_env_path": "/nonexistent/axiom-test-secrets.env",
    }
    data.update(overrides)
    return Settings.model_validate(data)


def test_require_gemini_rejects_empty_model_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "axiom_research.settings.load_gemini_api_key",
        lambda _path: "",
    )
    with pytest.raises(RuntimeError, match="GEMINI_MODEL"):
        require_gemini(_settings(gemini_model=""))
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        require_gemini(_settings(gemini_model="gemini-3.6-flash"))


def test_require_gemini_rejects_flash_lite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "axiom_research.settings.load_gemini_api_key",
        lambda _path: "test-key",
    )
    with pytest.raises(RuntimeError, match="Flash-Lite"):
        require_gemini(_settings(gemini_model="gemini-2.5-flash-lite"))


def test_build_gemini_model_uses_settings_not_baked_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "axiom_research.settings.load_gemini_api_key",
        lambda _path: "test-key",
    )
    cfg = _settings(gemini_model="gemini-3.6-flash")
    mock_cls = MagicMock(return_value=MagicMock(name="GeminiModel"))
    fake_mod = MagicMock(GeminiModel=mock_cls)
    with patch.dict(
        "sys.modules",
        {
            "strands": MagicMock(),
            "strands.models": MagicMock(),
            "strands.models.gemini": fake_mod,
        },
    ):
        model = build_gemini_model(cfg)
    assert model is mock_cls.return_value
    mock_cls.assert_called_once_with(
        client_args={"api_key": "test-key"},
        model_id="gemini-3.6-flash",
        params={"max_output_tokens": 4096},
    )


def test_token_cost_accounting_records_per_turn() -> None:
    accounting = TokenCostAccounting(input_usd_per_mtok=1.0, output_usd_per_mtok=2.0)
    turn = accounting.record_turn(
        agent_id="investigator",
        input_tokens=1_000_000,
        output_tokens=500_000,
    )
    assert turn.cost_usd == pytest.approx(2.0)
    assert accounting.total_tokens == 1_500_000
    assert accounting.total_cost_usd == pytest.approx(2.0)

    event = SimpleNamespace(
        agent=SimpleNamespace(name="planner"),
        stop_response=SimpleNamespace(
            message={"metadata": {"usage": {"inputTokens": 100, "outputTokens": 50}}}
        ),
    )
    assert usage_from_model_event(event) == {"input_tokens": 100, "output_tokens": 50}
    accounting.after_model_call(event)
    assert accounting.turns[-1].agent_id == "planner"
    assert accounting.turns[-1].total_tokens == 150

    agent = MagicMock()
    fake_hooks = MagicMock(AfterModelCallEvent=object, BeforeModelCallEvent=object)
    with patch.dict(
        "sys.modules",
        {"strands": MagicMock(), "strands.hooks": fake_hooks},
    ):
        accounting.attach(agent)
    assert agent.add_hook.call_count == 2
