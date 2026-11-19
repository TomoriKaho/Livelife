import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass, field
from urllib.parse import urlsplit

from app.core.config import _int_env


@dataclass(frozen=True)
class RetrievalSettings:
    mode: str = "keyword"
    base_url: str = ""
    api_key: str = field(default="", repr=False)
    model: str = "Qwen/Qwen3-Embedding-0.6B"
    model_revision: str = ""
    dimensions: int = 1024
    timeout_seconds: int = 10
    min_similarity: float = 0.55
    chunk_chars: int = 600
    overlap_chars: int = 80
    query_prefix: str = (
        "Instruct: Given a campus question, retrieve passages that provide evidence "
        "to answer the question.\nQuery: "
    )

    def __post_init__(self):
        if self.base_url:
            parsed = urlsplit(self.base_url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "EMBEDDING_BASE_URL must be an HTTP(S) base URL "
                    "without credentials, query or fragment"
                )
        if self.mode not in {"keyword", "hybrid"}:
            raise ValueError("RETRIEVAL_MODE must be keyword or hybrid")
        if not 1 <= self.dimensions <= 2000:
            raise ValueError("EMBEDDING_DIMENSIONS must be between 1 and 2000")
        if not math.isfinite(self.min_similarity) or not 0 <= self.min_similarity <= 1:
            raise ValueError("RETRIEVAL_MIN_SIMILARITY must be between 0 and 1")
        if not 100 <= self.chunk_chars <= 2000 or not 0 <= self.overlap_chars < self.chunk_chars:
            raise ValueError("invalid retrieval chunk size or overlap")
        if self.timeout_seconds < 1:
            raise ValueError("EMBEDDING_TIMEOUT_SECONDS must be positive")

    @property
    def profile(self) -> str:
        # Endpoint and thresholds do not change document vectors. Explicit revision
        # is mandatory operationally when replacing weights behind the same model ID.
        values = asdict(self)
        for key in ("mode", "base_url", "api_key", "timeout_seconds", "min_similarity"):
            values.pop(key)
        values["chunker_version"] = "paragraph-v2"
        return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def get_retrieval_settings() -> RetrievalSettings:
    return RetrievalSettings(
        mode=os.getenv("RETRIEVAL_MODE", "keyword").strip(),
        base_url=os.getenv("EMBEDDING_BASE_URL", "").strip().rstrip("/"),
        api_key=os.getenv("EMBEDDING_API_KEY", "").strip(),
        model=os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B").strip(),
        model_revision=os.getenv("EMBEDDING_MODEL_REVISION", "").strip(),
        dimensions=_int_env("EMBEDDING_DIMENSIONS", 1024, minimum=1),
        timeout_seconds=_int_env("EMBEDDING_TIMEOUT_SECONDS", 10, minimum=1),
        min_similarity=float(os.getenv("RETRIEVAL_MIN_SIMILARITY", "0.55")),
        chunk_chars=_int_env("RETRIEVAL_CHUNK_CHARS", 600, minimum=100),
        overlap_chars=_int_env("RETRIEVAL_OVERLAP_CHARS", 80, minimum=0),
        query_prefix=os.getenv("EMBEDDING_QUERY_PREFIX", RetrievalSettings.query_prefix),
    )
