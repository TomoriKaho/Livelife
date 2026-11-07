import re
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import InformationRecord


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
    score: int

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


def search_information(
    session: Session, question: str, *, limit: int = 8
) -> tuple[RetrievedInformation, ...]:
    terms = _terms(question)
    if not terms:
        return ()

    records = session.scalars(
        select(InformationRecord)
        .order_by(InformationRecord.fetched_at.desc(), InformationRecord.id.desc())
        .limit(500)
    ).all()
    ranked: list[RetrievedInformation] = []
    for row in records:
        title = (row.title or "").casefold()
        content = row.content.casefold()
        location = (row.activity_location or "").casefold()
        source_url = (row.source_url or "").casefold()
        platform = row.platform.casefold()
        source_id = row.source_id.casefold()
        activity_start = (
            row.activity_start_at.isoformat().casefold() if row.activity_start_at else ""
        )
        activity_end = row.activity_end_at.isoformat().casefold() if row.activity_end_at else ""
        registration_deadline = (
            row.registration_deadline_at.isoformat().casefold()
            if row.registration_deadline_at
            else ""
        )
        score = 0
        for term in terms:
            if term in title:
                score += 8
            if term in location:
                score += 5
            if term in source_url:
                score += 4
            if term in activity_start or term in activity_end or term in registration_deadline:
                score += 4
            if term in content:
                score += 2
            if term in platform or term in source_id:
                score += 1
        if score:
            ranked.append(
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
                    content=row.content[:3000],
                    score=score,
                )
            )
    ranked.sort(key=lambda item: (-item.score, item.published_at is None, item.id.hex))
    return tuple(ranked[:limit])
