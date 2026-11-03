"""LLM settings — same secrets file as travel-rag, stricter read path.

``GEMINI_MODEL`` and ``LLM_PROVIDER`` come from the project ``.env``.
Provider keys (``GEMINI_API_KEY``, ``MP_API_KEY``) are read **only** from
``SECRETS_ENV_PATH`` (``~/.config/rag/.env`` / Compose mount). They are not
Settings env fields, so project ``.env`` and process environment values are
ignored. Keys must never be baked into images.

There is no product auth token for MCP/api/web.
"""

from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic_settings import BaseSettings, SettingsConfigDict

# Must stay off Settings fields and out of Compose ``environment:`` / Dockerfiles.
PROVIDER_SECRET_NAMES: frozenset[str] = frozenset(
    {
        "GEMINI_API_KEY",
        "MP_API_KEY",
    }
)


def load_secret(secrets_env_path: str, name: str) -> str:
    """Read one secret from the secrets file only — never ``os.environ``."""
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
    # Host defaults for local Swarm MCP clients (Compose publishes 8210–8212).
    mcp_literature_url: str = "http://127.0.0.1:8210"
    mcp_materials_url: str = "http://127.0.0.1:8211"
    mcp_research_data_url: str = "http://127.0.0.1:8212"
    # Host-side default; Compose api uses http://verifier:9000 via VERIFIER_URL.
    verifier_url: str = "http://127.0.0.1:8201"
    verifier_timeout_seconds: float = 60.0

    # Swarm budgets (0.A defaults; tighter than Strands SDK defaults).
    swarm_max_handoffs: int = 8
    swarm_max_iterations: int = 8
    swarm_execution_timeout_seconds: float = 180.0
    swarm_node_timeout_seconds: float = 45.0
    swarm_repetitive_handoff_detection: bool = True
    swarm_repetitive_handoff_detection_window: int = 8
    swarm_repetitive_handoff_min_unique_agents: int = 3
    swarm_max_tokens_per_run: int = 100_000
    swarm_max_cost_usd_per_run: float = 1.0
    # Operator-overridable Flash pricing for Swarm token/cost accounting (USD / 1M tokens).
    gemini_input_usd_per_mtok: float = 0.30
    gemini_output_usd_per_mtok: float = 2.50

    @property
    def gemini_api_key(self) -> str:
        return load_gemini_api_key(self.secrets_env_path)

    @property
    def mp_api_key(self) -> str:
        return load_mp_api_key(self.secrets_env_path)


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
