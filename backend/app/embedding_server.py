"""Optional, separately deployed embedding service; not imported by the API app."""

import hmac
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services.retrieval.config import get_retrieval_settings


class EmbeddingRequest(BaseModel):
    model: str
    input: list[str] = Field(min_length=1, max_length=16)
    encoding_format: str = "float"

    @field_validator("input")
    @classmethod
    def bounded_input(cls, texts):
        if any(not text.strip() or len(text) > 8000 for text in texts):
            raise ValueError("embedding inputs must contain 1 to 8000 characters")
        return texts


@asynccontextmanager
async def lifespan(app):
    from sentence_transformers import SentenceTransformer

    settings = get_retrieval_settings()
    if not settings.model_revision:
        raise RuntimeError("EMBEDDING_MODEL_REVISION must pin a model revision")
    model = SentenceTransformer(
        settings.model,
        revision=settings.model_revision,
        device=os.getenv("EMBEDDING_DEVICE", "cpu"),
        trust_remote_code=False,
    )
    if model.get_sentence_embedding_dimension() != settings.dimensions:
        raise RuntimeError("EMBEDDING_DIMENSIONS does not match the selected model")
    # Bound compute consistently for document chunks and both benchmark candidates.
    model.max_seq_length = min(1024, model.max_seq_length)
    app.state.encoder = model
    app.state.settings = settings
    app.state.lock = threading.Lock()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ready",
        "model": app.state.settings.model,
        "revision": app.state.settings.model_revision,
    }


@app.post("/v1/embeddings")
def embeddings(body: EmbeddingRequest, authorization: str = Header(default="")):
    settings = app.state.settings
    if settings.api_key and not hmac.compare_digest(
        authorization.encode(), ("Bearer " + settings.api_key).encode()
    ):
        raise HTTPException(401, "authentication_required")
    if body.model != settings.model or body.encoding_format != "float":
        raise HTTPException(400, "unsupported_model_or_encoding")
    if not app.state.lock.acquire(blocking=False):
        raise HTTPException(429, "embedding_busy", headers={"Retry-After": "2"})
    try:
        # No query prefix is added here: the calling adapter supplies model-specific instructions.
        result = app.state.encoder.encode(
            body.input, normalize_embeddings=True, show_progress_bar=False
        )
        return {
            "model": settings.model,
            "revision": settings.model_revision,
            "data": [
                {"object": "embedding", "index": index, "embedding": vector.tolist()}
                for index, vector in enumerate(result)
            ],
        }
    finally:
        app.state.lock.release()
