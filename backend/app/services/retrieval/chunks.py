import re
from dataclasses import dataclass
from uuid import UUID

from app.services.retrieval.config import RetrievalSettings


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    start: int
    end: int
    body: str
    text: str
    information_id: UUID
    source_url: str | None


def context_header(record, *, include_identity=True) -> str:
    fields = (
        ("标题", record.title),
        ("来源", record.source_name or record.platform),
        ("原记录", str(record.id)),
        ("原文", record.source_url),
        ("地点", record.activity_location),
        ("发布日期", record.published_at),
        ("活动日期", record.activity_date),
        ("开始", record.activity_start_at),
        ("结束", record.activity_end_at),
        ("报名截止", record.registration_deadline_at),
    )
    return "\n".join(
        f"{key}: {value}"
        for key, value in fields
        if value is not None and (include_identity or key not in {"原记录", "原文"})
    )


def split_record(record, settings: RetrievalSettings) -> list[Chunk]:
    body = record.content
    # Machine IDs and URLs remain explicit metadata, not semantic model input.
    header = context_header(record, include_identity=False)
    chunks = []
    start = 0
    while start < len(body):
        end = min(start + settings.chunk_chars, len(body))
        if end < len(body):
            # Prefer paragraph or sentence endings, while guaranteeing progress.
            boundaries = list(re.finditer(r"\n+|[。！？；]", body[start:end]))
            useful = [m.end() for m in boundaries if m.end() >= settings.chunk_chars // 2]
            if useful:
                end = start + useful[-1]
        part = body[start:end]
        if part.strip():
            chunks.append(
                Chunk(
                    len(chunks),
                    start,
                    end,
                    part,
                    header + "\n正文:\n" + part,
                    record.id,
                    record.source_url,
                )
            )
        if end == len(body):
            break
        start = max(start + 1, end - settings.overlap_chars)
    return chunks
