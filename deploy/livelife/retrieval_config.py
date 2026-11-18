"""Server-owned opt-in for local test embeddings, separate from chat credentials."""

import json
import re
from pathlib import Path

from .branch_database import branch_name
from .mail_config import private_path

INVALID = "invalid retrieval configuration; inspect credentials/retrieval.json privately"
MODEL = "Qwen/Qwen3-Embedding-0.6B"
REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"


def private_json(path):
    private_path(path.parent, directory=True)
    if private_path(path).st_size > 16384:
        raise ValueError(INVALID)
    return json.loads(path.read_text())


def service_settings(root, service):
    if not isinstance(service, str) or not re.fullmatch(r"embedding-[0-9a-f]{16}", service):
        raise ValueError(INVALID)
    directory = Path(root) / "embedding" / service
    if directory.parent.is_symlink():
        raise ValueError(INVALID)
    value = private_json(directory / "service.json")
    if not isinstance(value, dict) or set(value) != {"source_sha", "model", "revision", "dimensions", "port", "threads", "key"}:
        raise ValueError(INVALID)
    if (not isinstance(value["source_sha"], str) or not re.fullmatch(r"[0-9a-f]{40}", value["source_sha"])
            or value["model"] != MODEL or value["revision"] != REVISION
            or value["dimensions"] != 1024
            or type(value["port"]) is not int or not 19000 <= value["port"] < 20000
            or type(value["threads"]) is not int or not 1 <= value["threads"] <= 8
            or not isinstance(value["key"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["key"])):
        raise ValueError(INVALID)
    return value


def model_environment(value):
    return {
        "EMBEDDING_MODEL": value["model"],
        "EMBEDDING_MODEL_REVISION": value["revision"],
        "EMBEDDING_DIMENSIONS": str(value["dimensions"]),
        "EMBEDDING_API_KEY": value["key"],
        "EMBEDDING_DEVICE": "cpu",
        "OMP_NUM_THREADS": str(value["threads"]),
    }


def load(root, branch):
    path = Path(root) / "credentials/retrieval.json"
    if path.parent.is_symlink():
        raise ValueError(INVALID)
    if not path.exists() and not path.is_symlink():
        return {}
    try:
        value = private_json(path)
        if set(value) != {"branches", "service"} or not isinstance(value["branches"], list):
            raise ValueError(INVALID)
        for name in value["branches"]:
            branch_name(name)
        service = service_settings(root, value["service"])
        if branch not in value["branches"]:
            return {}
        return {
            **{k: v for k, v in model_environment(service).items()
               if k not in {"EMBEDDING_DEVICE", "OMP_NUM_THREADS"}},
            "EMBEDDING_BASE_URL": f"http://127.0.0.1:{service['port']}/v1",
            "EMBEDDING_TIMEOUT_SECONDS": "10",
            "RETRIEVAL_MODE": "hybrid",
            "RETRIEVAL_MIN_SIMILARITY": "0.55",
            "RETRIEVAL_CHUNK_CHARS": "600",
            "RETRIEVAL_OVERLAP_CHARS": "80",
        }
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        raise ValueError(INVALID) from None
