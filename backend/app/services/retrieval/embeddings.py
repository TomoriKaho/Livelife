import math

import httpx

from app.services.retrieval.config import RetrievalSettings


class EmbeddingError(RuntimeError):
    """Stable error code only: never expose upstream text, URLs or credentials."""


def validate_vector(value, dimensions: int) -> list[float]:
    if not isinstance(value, list) or len(value) != dimensions:
        raise EmbeddingError("embedding_dimensions")
    try:
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
            raise EmbeddingError("embedding_invalid_vector")
        norm = math.hypot(*value)
    except OverflowError as error:
        raise EmbeddingError("embedding_invalid_vector") from error
    if not math.isfinite(norm) or norm == 0:
        raise EmbeddingError("embedding_invalid_vector")
    return [v / norm for v in value]


class EmbeddingClient:
    def __init__(self, settings: RetrievalSettings, *, transport=None):
        self.settings = settings
        self.transport = transport

    def encode(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        if not texts:
            return []
        if not self.settings.base_url:
            raise EmbeddingError("embedding_not_configured")
        if len(texts) > 16:
            raise ValueError("at most 16 embedding inputs per request")
        inputs = [self.settings.query_prefix + t for t in texts] if query else texts
        headers = (
            {"Authorization": f"Bearer {self.settings.api_key}"} if self.settings.api_key else {}
        )
        try:
            with httpx.Client(
                timeout=self.settings.timeout_seconds,
                transport=self.transport,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                # Bound the response before parsing; normal 16 x 1024 vectors are much smaller.
                with client.stream(
                    "POST",
                    self.settings.base_url + "/embeddings",
                    headers=headers,
                    json={
                        "model": self.settings.model,
                        "input": inputs,
                        "encoding_format": "float",
                    },
                ) as response:
                    response.raise_for_status()
                    data = bytearray()
                    for part in response.iter_bytes():
                        data.extend(part)
                        if len(data) > 4_000_000:
                            raise EmbeddingError("embedding_response_too_large")
                import json

                payload = json.loads(data)
            if not isinstance(payload, dict):
                raise EmbeddingError("embedding_invalid_response")
            if payload.get("model", self.settings.model) != self.settings.model:
                raise EmbeddingError("embedding_model_mismatch")
            if (
                self.settings.model_revision
                and payload.get("revision", self.settings.model_revision)
                != self.settings.model_revision
            ):
                raise EmbeddingError("embedding_revision_mismatch")
            rows = payload["data"]
            if not isinstance(rows, list) or len(rows) != len(texts):
                raise EmbeddingError("embedding_response_count")
            by_index = {}
            for row in rows:
                index = row["index"]
                if type(index) is not int or index not in range(len(texts)) or index in by_index:
                    raise EmbeddingError("embedding_response_index")
                by_index[index] = validate_vector(row["embedding"], self.settings.dimensions)
            return [by_index[index] for index in range(len(texts))]
        except httpx.HTTPError as error:
            raise EmbeddingError("embedding_unavailable") from error
        except (ValueError, KeyError, TypeError) as error:
            raise EmbeddingError("embedding_invalid_response") from error


class PreparedQuery:
    """One request's vector, computed before account/IP admission locks are held."""

    def __init__(self, question: str, client: EmbeddingClient):
        self.question = question
        try:
            self.vectors = client.encode([question], query=True)
            self.error = None
        except EmbeddingError as error:
            self.vectors = []
            self.error = str(error)

    def encode(self, texts, *, query=False):
        if self.error:
            raise EmbeddingError(self.error)
        if not query or texts != [self.question]:
            # History changed between preflight and admission: use fresh keywords,
            # never a mismatched vector or another external call inside the lock.
            raise EmbeddingError("embedding_context_changed")
        return self.vectors

    @classmethod
    def skipped(cls):
        prepared = cls.__new__(cls)
        prepared.question = ""
        prepared.vectors = []
        prepared.error = "embedding_preflight_skipped"
        return prepared
