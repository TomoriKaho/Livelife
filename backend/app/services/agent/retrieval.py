import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import Float, case, cast, func, literal, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import InformationRecord, RetrievalChunk, RetrievalState
from app.db.vector import Vector
from app.services.retrieval.chunks import context_header, split_record
from app.services.retrieval.config import RetrievalSettings, get_retrieval_settings
from app.services.retrieval.constraints import constraints
from app.services.retrieval.embeddings import EmbeddingClient, EmbeddingError


@dataclass(frozen=True)
class RetrievedInformation:
    id: UUID
    title: str | None
    source_url: str | None
    platform: str
    source_id: str
    published_at: object | None
    activity_location: str | None
    activity_start_at: object | None
    activity_end_at: object | None
    registration_deadline_at: object | None
    content: str
    score: float

    def citation(self, rank: int) -> dict:
        body = self.content.strip()
        parsed_url = urlparse(self.source_url or "")
        safe_url = (
            self.source_url
            if parsed_url.scheme in {"http", "https"} and parsed_url.netloc
            else None
        )
        return {
            "rank": rank,
            "information_id": str(self.id),
            "title": self.title,
            "source_url": safe_url,
            "platform": self.platform,
            "source_id": self.source_id,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "activity_location": self.activity_location,
            "activity_start_at": self.activity_start_at.isoformat()
            if self.activity_start_at
            else None,
            "activity_end_at": self.activity_end_at.isoformat() if self.activity_end_at else None,
            "registration_deadline_at": self.registration_deadline_at.isoformat()
            if self.registration_deadline_at
            else None,
            "snippet": body[:500],
        }


def _terms(question: str) -> tuple[str, ...]:
    runs = re.findall(r"[a-z0-9]+|[\u3400-\u9fff]+", question.casefold())
    terms: list[str] = []
    for run in runs:
        if len(run) < 2:
            continue
        if re.fullmatch(r"[\u3400-\u9fff]+", run):
            terms.extend(run[index : index + 2] for index in range(len(run) - 1))
        else:
            terms.append(run)
    return tuple(dict.fromkeys(terms))


logger = logging.getLogger(__name__)
STOP_TERMS = frozenset(
    {
        "今天",
        "明天",
        "昨天",
        "现在",
        "此刻",
        "正在",
        "什么",
        "有什",
        "么课",
        "怎么",
        "哪里",
        "在哪",
        "是谁",
        "这个",
        "一下",
        "请问",
        "想知",
        "知道",
        "能不",
        "不能",
        "多少",
        "几点",
    }
)


def _keyword_candidates(session, question, query, pinned_ids):
    lexical = re.sub(
        r"是什么|有什么|怎么|哪里|在哪|请问|今天|明天|昨天|现在|此刻|正在", " ", question
    )
    terms = tuple(t for t in _terms(lexical) if t not in STOP_TERMS)[:64]
    primary_terms = terms
    terms = tuple(dict.fromkeys((*terms, *query.aliases)))
    if not terms and not pinned_ids and not query.structured:
        return [], terms
    score = literal(0)
    for column, weight in (
        (InformationRecord.title, 8),
        (InformationRecord.activity_location, 5),
        (InformationRecord.content, 2),
        (InformationRecord.source_name, 1),
    ):
        for term in terms:
            score += case((column.icontains(term, autoescape=True), weight), else_=0)
    if pinned_ids:
        score += case((InformationRecord.id.in_(pinned_ids), 30), else_=0)
    if query.structured and not terms:
        score += 1
    coverage = literal(0)
    for term in primary_terms:
        coverage += case(
            (
                or_(
                    InformationRecord.title.icontains(term, autoescape=True),
                    InformationRecord.content.icontains(term, autoescape=True),
                    InformationRecord.activity_location.icontains(term, autoescape=True),
                ),
                1,
            ),
            else_=0,
        )
    eligible = (
        or_(
            coverage >= max(1, math.ceil(len(primary_terms) * 0.35)),
            InformationRecord.id.in_(pinned_ids),
        )
        if primary_terms and not query.structured
        else literal(True)
    )
    rows = session.execute(
        select(InformationRecord, score.label("keyword_score"))
        .where(query.clause, score > 0, eligible)
        .order_by(score.desc(), InformationRecord.id)
        .limit(64)
        .execution_options(populate_existing=True)
    ).all()
    return rows, terms


def _vector_candidates(session, query, vector, settings):
    if session.get_bind().dialect.name != "postgresql":
        raise EmbeddingError("vector_requires_postgresql")
    c = RetrievalChunk
    distance = c.embedding.op("<=>", return_type=Float)(
        cast(literal(json.dumps(vector, allow_nan=False)), Vector())
    )
    # Rank chunks per original record before limiting: one long article must not
    # consume every vector candidate. All filters apply before the top-k selection.
    ranked = (
        select(
            c.information_id,
            c.body,
            distance.label("distance"),
            func.row_number()
            .over(partition_by=c.information_id, order_by=(distance, c.ordinal))
            .label("chunk_rank"),
        )
        .join(RetrievalState, RetrievalState.information_id == c.information_id)
        .join(InformationRecord, InformationRecord.id == c.information_id)
        .where(
            query.clause,
            c.profile == settings.profile,
            RetrievalState.profile == settings.profile,
            c.revision == RetrievalState.revision,
            RetrievalState.indexed_revision == RetrievalState.revision,
        )
        .subquery()
    )
    return session.execute(
        select(InformationRecord, ranked.c.body, ranked.c.distance)
        .join(ranked, ranked.c.information_id == InformationRecord.id)
        .where(ranked.c.chunk_rank == 1, ranked.c.distance <= 1 - settings.min_similarity)
        .order_by(ranked.c.distance, InformationRecord.id)
        .limit(64)
        .execution_options(populate_existing=True)
    ).all()


def search_information(
    session: Session,
    question: str,
    *,
    limit: int = 8,
    pinned_ids: tuple = (),
    now: datetime | None = None,
    settings: RetrievalSettings | None = None,
    embedding_client=None,
    diagnostics: dict | None = None,
    constraint_question: str | None = None,
) -> tuple[RetrievedInformation, ...]:
    if not 1 <= limit <= 8:
        raise ValueError("retrieval limit must be between 1 and 8")
    settings = settings or get_retrieval_settings()
    diagnostics = diagnostics if diagnostics is not None else {}
    diagnostics.update(mode="keyword", reason="configured_keyword")
    query = constraints(
        session, constraint_question if constraint_question is not None else question, now
    )
    keyword, terms = _keyword_candidates(session, question, query, pinned_ids)
    vectors = []
    if settings.mode == "hybrid":
        try:
            client = embedding_client or EmbeddingClient(settings)
            vector = client.encode([question], query=True)[0]
            # A failed optional vector SELECT must not poison the caller's transaction.
            with session.begin_nested():
                vectors = _vector_candidates(session, query, vector, settings)
            diagnostics.update(mode="hybrid", reason=None, vector_candidates=len(vectors))
            logger.info("retrieval_hybrid keyword=%d vector=%d", len(keyword), len(vectors))
        except (EmbeddingError, SQLAlchemyError) as error:
            code = str(error) if isinstance(error, EmbeddingError) else "vector_query_failed"
            diagnostics.update(mode="keyword", reason=code)
            logger.warning("retrieval_degraded mode=keyword reason=%s", code)
    combined = {}
    for rank, (row, lexical_score) in enumerate(keyword, 1):
        chunks = split_record(row, settings)
        best = max(
            chunks, key=lambda chunk: sum(t in chunk.body.casefold() for t in terms), default=None
        )
        combined[row.id] = [
            row,
            best.body if best else row.content[: settings.chunk_chars],
            1 / (60 + rank),
            lexical_score,
        ]
    for rank, (row, body, distance) in enumerate(vectors, 1):
        if row.id in combined:
            combined[row.id][1] = body
            combined[row.id][2] += 1 / (60 + rank)
        else:
            combined[row.id] = [row, body, 1 / (60 + rank), 0]
    # Explicit follow-up records remain preferred, but cannot bypass fresh filters.
    ordered = sorted(
        combined.values(),
        key=lambda item: (item[0].id not in pinned_ids, -item[2], -item[3], item[0].id.hex),
    )
    return tuple(
        RetrievedInformation(
            id=row.id,
            title=row.title,
            source_url=row.source_url,
            platform=row.platform,
            source_id=row.source_id,
            published_at=row.published_at,
            activity_location=row.activity_location,
            activity_start_at=row.activity_start_at,
            activity_end_at=row.activity_end_at,
            registration_deadline_at=row.registration_deadline_at,
            content=body + "\n资料背景:\n" + context_header(row),
            score=score,
        )
        for row, body, score, _ in ordered[:limit]
    )
