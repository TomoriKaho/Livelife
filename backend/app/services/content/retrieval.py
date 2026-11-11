"""Produce stable, source-linked text chunks for Agent and embedding jobs."""

from hashlib import sha256

from pydantic import BaseModel

from app.schemas.information import Information

CHUNK_CHARS = 480
OVERLAP_CHARS = 60


class InformationChunk(BaseModel):
    ordinal: int
    text: str
    text_sha256: str


class RetrievalDocument(BaseModel):
    information: Information
    chunking_version: str = "chars-v1"
    chunks: tuple[InformationChunk, ...]


def retrieval_document(information: Information) -> RetrievalDocument:
    chunks = []
    prefix = f"{information.title}\n\n" if information.title else ""
    start = 0
    while start < len(information.content):
        end = min(start + CHUNK_CHARS, len(information.content))
        text = prefix + information.content[start:end]
        chunks.append(
            InformationChunk(
                ordinal=len(chunks),
                text=text,
                text_sha256=sha256(text.encode("utf-8")).hexdigest(),
            )
        )
        if end == len(information.content):
            break
        start = end - OVERLAP_CHARS
    return RetrievalDocument(information=information, chunks=tuple(chunks))
