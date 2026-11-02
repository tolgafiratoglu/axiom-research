"""Strands ``GeminiModel`` wired to ``axiom_research.settings``.

Model ID comes only from ``GEMINI_MODEL``. API key only from
``SECRETS_ENV_PATH``. Nothing is baked into source.
"""

from __future__ import annotations

from typing import Any

from axiom_research.settings import Settings, require_gemini, settings

_MAX_OUTPUT_TOKENS = 4096


def build_gemini_model(cfg: Settings | None = None) -> Any:
    """Build a Strands ``GeminiModel`` or raise if Gemini config is incomplete."""
    ready = require_gemini(cfg or settings)
    from strands.models.gemini import GeminiModel

    # Gemini 3.x: do not send temperature / top_p / top_k (same as GeminiProvider).
    return GeminiModel(
        client_args={"api_key": ready.gemini_api_key},
        model_id=ready.gemini_model.strip(),
        params={"max_output_tokens": _MAX_OUTPUT_TOKENS},
    )
