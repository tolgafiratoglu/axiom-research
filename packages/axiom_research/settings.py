"""LLM settings — same secrets file as travel-rag, stricter read path.

``GEMINI_MODEL`` and ``LLM_PROVIDER`` come from the project ``.env``.
``GEMINI_API_KEY`` is read only from ``SECRETS_ENV_PATH``
(``~/.config/rag/.env``). It is not an env-backed Settings field, so a
project ``.env`` or process ``GEMINI_API_KEY`` is ignored.

There is no product auth token for MCP/api/web.
"""

from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic_settings import BaseSettings, SettingsConfigDict


def load_secret(secrets_env_path: str, name: str) -> str:
    path = Path(secrets_env_path).expanduser()
    if not path.is_file():
        return ""
    return (dotenv_values(path).get(name) or "").strip()


def load_gemini_api_key(secrets_env_path: str) -> str:
    return load_secret(secrets_env_path, "GEMINI_API_KEY")


def load_mp_api_key(secrets_env_path: str) -> str:
    return load_secret(secrets_env_path, "MP_API_KEY")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: Literal["gemini"] = "gemini"
    gemini_model: str = ""
    secrets_env_path: str = "~/.config/rag/.env"
    database_url: str = "postgresql://axiom:axiom@127.0.0.1:5434/axiom_research"
    # Operator-overridable Flash pricing for Swarm token/cost accounting (USD / 1M tokens).
    gemini_input_usd_per_mtok: float = 0.30
    gemini_output_usd_per_mtok: float = 2.50

    @property
    def gemini_api_key(self) -> str:
        return load_gemini_api_key(self.secrets_env_path)


def require_gemini(settings: Settings) -> Settings:
    model = (settings.gemini_model or "").strip()
    if not model:
        raise RuntimeError(
            "GEMINI_MODEL is unset or empty. Set a currently supported Gemini "
            "Flash ID in the project .env (not Flash-Lite; do not use retired "
            "IDs such as gemini-3.5-flash)."
        )
    lowered = model.lower().replace("_", "-")
    if "flash-lite" in lowered:
        raise RuntimeError(
            "GEMINI_MODEL must be a Gemini Flash ID, not Flash-Lite "
            f"(got {model!r})."
        )
    if "flash" not in lowered:
        raise RuntimeError(
            "GEMINI_MODEL must be a Gemini Flash family ID "
            f"(got {model!r})."
        )
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Add it to "
            f"{settings.secrets_env_path} (not the project .env)."
        )
    if settings.llm_provider != "gemini":
        raise RuntimeError("LLM_PROVIDER must be gemini.")
    return settings


settings = Settings()
