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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: Literal["gemini"] = "gemini"
    gemini_model: str = ""
    secrets_env_path: str = "~/.config/rag/.env"

    @property
    def gemini_api_key(self) -> str:
        return load_gemini_api_key(self.secrets_env_path)


def require_gemini(settings: Settings) -> Settings:
    if not (settings.gemini_model or "").strip():
        raise RuntimeError(
            "GEMINI_MODEL is unset or empty. Set a currently supported Gemini "
            "Flash ID in the project .env (not Flash-Lite; do not use retired "
            "IDs such as gemini-3.5-flash)."
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
