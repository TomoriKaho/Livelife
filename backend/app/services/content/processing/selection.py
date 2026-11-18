"""Convert exact source selections into the internal, typed candidate."""

import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.information import InformationInput
from app.services.content.processing.schemas import Candidate, Evidence, EvidenceError


class Quote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quote: str = Field(min_length=1, max_length=500)


class Selection(Candidate):
    # Only a contiguous location span: no model-written location value or coordinates.
    activity_location: Quote | None = None


def convert_selection(selected: Selection, source: InformationInput) -> Candidate:
    data = selected.model_dump()
    for field in (
        "activity_date",
        "activity_start_at",
        "activity_end_at",
        "registration_deadline_at",
    ):
        evidence = getattr(selected, field)
        if evidence is None:
            continue
        if evidence.quote not in source.content or evidence.value not in evidence.quote:
            raise EvidenceError("selection_not_in_original")
        quote = unicodedata.normalize("NFKC", evidence.quote)
        dates = {
            tuple(map(int, match))
            for match in re.findall(r"(\d{4})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})", quote)
        }
        if len(dates) != 1:
            raise EvidenceError("selection_date_ambiguous")
        day = date(*next(iter(dates)))
        if field == "activity_date":
            # The selected value itself must contain the explicit date.
            if not re.search(r"\d{4}\s*[年./-]", unicodedata.normalize("NFKC", evidence.value)):
                raise EvidenceError("selection_date_missing")
            value = day.isoformat()
        else:
            clock = re.fullmatch(
                r"\s*(\d{1,2})\s*:\s*(\d{2})\s*", unicodedata.normalize("NFKC", evidence.value)
            )
            if not clock:
                raise EvidenceError("selection_time_unsupported")
            hour, minute = map(int, clock.groups())
            value = datetime(
                day.year, day.month, day.day, hour, minute, tzinfo=timezone(timedelta(hours=8))
            ).isoformat()
        data[field] = Evidence(value=value, quote=evidence.quote).model_dump()
    if selected.activity_location:
        quote = selected.activity_location.quote
        if not quote.strip() or quote not in source.content:
            raise EvidenceError("selection_not_in_original")
        data["activity_location"] = Evidence(value=quote, quote=quote).model_dump()
    return Candidate.model_validate(data)
