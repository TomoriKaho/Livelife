"""Explicit, immutable-version opt-in for server-owned test model credentials."""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from .mail_config import private_path

INVALID = "invalid model configuration; check credentials/model.json privately"
REQUIRED = {"AGENT_LLM_BASE_URL", "AGENT_LLM_API_KEY", "AGENT_LLM_MODEL"}
FIELDS = REQUIRED | {
    "AGENT_LLM_REASONING_EFFORT",
    "AGENT_LLM_TIMEOUT_SECONDS",
    "AGENT_LLM_MAX_OUTPUT_TOKENS",
    "HTTPS_PROXY",
}


def validate(value):
    if not isinstance(value, dict) or set(value) != {"trusted_shas", "environment"}:
        raise ValueError(INVALID)
    shas, env = value["trusted_shas"], value["environment"]
    if not isinstance(shas, list) or any(
        not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha)
        for sha in shas
    ):
        raise ValueError(INVALID)
    if not isinstance(env, dict) or not REQUIRED <= env.keys() <= FIELDS:
        raise ValueError(INVALID)
    if any(
        not isinstance(item, str)
        or not item.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in item)
        for item in env.values()
    ):
        raise ValueError(INVALID)
    base = urlsplit(env["AGENT_LLM_BASE_URL"])
    if base.scheme != "https" or not base.hostname or base.username or base.password:
        raise ValueError(INVALID)
    if env.get("AGENT_LLM_REASONING_EFFORT", "") not in {
        "",
        "none",
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
        "max",
    }:
        raise ValueError(INVALID)
    for field in ("AGENT_LLM_TIMEOUT_SECONDS", "AGENT_LLM_MAX_OUTPUT_TOKENS"):
        if field in env and (
            not env[field].isascii() or not env[field].isdigit() or int(env[field]) < 1
        ):
            raise ValueError(INVALID)
    if "HTTPS_PROXY" in env:
        proxy = urlsplit(env["HTTPS_PROXY"])
        if proxy.scheme != "http" or proxy.hostname != "127.0.0.1" or not proxy.port:
            raise ValueError(INVALID)
    return shas, dict(env)


def load(root, ident):
    directory = Path(root) / "credentials"
    path = directory / "model.json"
    if directory.is_symlink():
        raise ValueError(INVALID)
    if not path.exists() and not path.is_symlink():
        return {}
    try:
        private_path(directory, directory=True)
        if private_path(path).st_size > 16384:
            raise ValueError(INVALID)
        shas, env = validate(json.loads(path.read_text(encoding="utf-8")))
        if ident not in {"be-" + sha for sha in shas}:
            return {}
        if "HTTPS_PROXY" in env:
            env["NO_PROXY"] = "localhost,127.0.0.1,::1"
        return env
    except (OSError, ValueError, UnicodeError):
        raise ValueError(INVALID) from None
