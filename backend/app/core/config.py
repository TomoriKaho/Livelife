import os
from dataclasses import dataclass

from app.core.environment import load_backend_environment

load_backend_environment()


def get_database_url() -> str | None:
    value = os.getenv("DATABASE_URL", "").strip()
    return value or None


def get_agent_settings() -> "AgentSettings":
    return AgentSettings(
        session_secret=os.getenv("AGENT_SESSION_SECRET", "").strip(),
        llm_base_url=os.getenv("AGENT_LLM_BASE_URL", "").strip().rstrip("/"),
        llm_api_key=os.getenv("AGENT_LLM_API_KEY", "").strip(),
        llm_model=os.getenv("AGENT_LLM_MODEL", "").strip(),
        llm_reasoning_effort=_reasoning_effort(),
        llm_timeout_seconds=_int_env("AGENT_LLM_TIMEOUT_SECONDS", 60, minimum=1),
        max_output_tokens=_int_env("AGENT_LLM_MAX_OUTPUT_TOKENS", 1024, minimum=1),
        max_message_chars=_int_env("AGENT_MAX_MESSAGE_CHARS", 4000, minimum=1),
        max_context_chars=_int_env("AGENT_MAX_CONTEXT_CHARS", 24000, minimum=1000),
        requests_per_minute=_int_env("AGENT_RATE_REQUESTS_PER_WINDOW", 5, minimum=1),
        ip_requests_per_hour=_int_env("AGENT_IP_REQUESTS_PER_HOUR", 30, minimum=1),
        daily_token_quota=_int_env("AGENT_DAILY_TOKEN_QUOTA", 100000, minimum=1),
    )


def _reasoning_effort() -> str:
    value = os.getenv("AGENT_LLM_REASONING_EFFORT", "").strip()
    if value not in {"", "none", "minimal", "low", "medium", "high", "xhigh", "max"}:
        raise RuntimeError("AGENT_LLM_REASONING_EFFORT is invalid")
    return value


def _int_env(name: str, default: int, *, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer") from error
    if value < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}")
    return value


@dataclass(frozen=True)
class AgentSettings:
    session_secret: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_seconds: int
    max_output_tokens: int
    max_message_chars: int
    max_context_chars: int
    requests_per_minute: int
    ip_requests_per_hour: int
    daily_token_quota: int
    llm_reasoning_effort: str = ""

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)
