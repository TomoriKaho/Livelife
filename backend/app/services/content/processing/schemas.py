"""Internal, versioned extraction contract; never accepts model tools or coordinates."""

import re
import unicodedata
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.information import InformationInput

VERSION = "campus-extraction-v5"
FIELDS = (
    "activity_date",
    "activity_start_at",
    "activity_end_at",
    "registration_deadline_at",
    "activity_location",
)


class EvidenceError(ValueError):
    """A fixed validation code safe for task diagnostics."""


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1, max_length=500)
    quote: str = Field(min_length=1, max_length=2000)


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["single_event", "multiple_events", "article", "uncertain"]
    summary: str = Field(max_length=2000)
    summary_quotes: list[str] = Field(max_length=10)
    activity_date: Evidence | None = None
    activity_start_at: Evidence | None = None
    activity_end_at: Evidence | None = None
    registration_deadline_at: Evidence | None = None
    activity_location: Evidence | None = None
    notices: list[str] = Field(default_factory=list, max_length=20)
    ambiguities: list[str] = Field(default_factory=list, max_length=20)


def location_layout(value: str) -> str:
    """Only fold bracket layout and a house-number space, not word/line separators."""
    value = re.sub(r"\s*([（(])\s*", r"\1", value)
    value = re.sub(r"\s*([）)])", r"\1", value)
    value = re.sub(r"(?<=\d)[ \t\u3000]+(?=号)", "", value)
    return re.sub(r"(?<=[街路巷])[ \t\u3000]+(?=\d+号)", "", value).strip()


def validate_candidate(candidate: Candidate, original: InformationInput) -> InformationInput:
    """Check source spans/types. Semantic correctness still requires a human review."""
    text = original.content
    if candidate.summary and not candidate.summary_quotes:
        raise EvidenceError("summary_without_evidence")
    if any(
        not q.strip() or (q not in text and q != original.title) for q in candidate.summary_quotes
    ):
        raise EvidenceError("invalid_summary_evidence")
    fields = {}
    for name in FIELDS:
        evidence = getattr(candidate, name)
        fields[name] = None
        if evidence is None:
            continue
        if candidate.kind != "single_event":
            raise EvidenceError("non_single_event_fields")
        if evidence.quote not in text:
            raise EvidenceError("evidence_not_in_original")
        if name == "activity_location":
            if not evidence.value.strip() or evidence.value not in evidence.quote:
                raise EvidenceError("location_not_in_evidence")
        else:
            # Do not infer a year from publication time. Unsupported expressions remain null.
            value = (
                date.fromisoformat(evidence.value)
                if name == "activity_date"
                else datetime.fromisoformat(evidence.value)
            )
            quote = unicodedata.normalize("NFKC", evidence.quote)
            dates = re.findall(r"(\d{4})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})", quote)
            if (str(value.year), str(value.month), str(value.day)) not in [
                tuple(str(int(part)) for part in match) for match in dates
            ]:
                raise EvidenceError("date_not_explicit_in_evidence")
            if isinstance(value, datetime):
                # v1 is explicitly a Beijing-time campus extractor.
                from datetime import timedelta

                if value.utcoffset() != timedelta(hours=8):
                    raise EvidenceError("expected_beijing_time")
                times = re.findall(r"(\d{1,2})\s*:\s*(\d{2})", quote)
                if (value.hour, value.minute) not in [(int(h), int(m)) for h, m in times]:
                    raise EvidenceError("time_not_explicit_in_evidence")
                if value.second or value.microsecond:
                    raise EvidenceError("unsupported_time_precision")
        fields[name] = (
            re.sub(r"\s+", " ", location_layout(evidence.value)).strip()
            if name == "activity_location"
            else evidence.value
        )
    payload = original.model_dump(mode="json")
    payload.update(fields, place_id=None)
    result = InformationInput.model_validate(payload)
    if result.activity_date and result.activity_start_at:
        from zoneinfo import ZoneInfo

        if (
            result.activity_start_at.astimezone(ZoneInfo("Asia/Shanghai")).date()
            != result.activity_date
        ):
            raise EvidenceError("activity_date_conflict")
    return result
