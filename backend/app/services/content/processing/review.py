"""Explicit review gates and evidence-preserving manual fallback contracts."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.information import InformationInput
from app.services.content.locations import LocationResolver
from app.services.content.processing.schemas import FIELDS, Candidate, validate_candidate
from app.services.content.processing.selection import Selection


class FallbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_job_id: UUID
    source_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    selection: Selection
    resolutions: dict[str, str] = Field(default_factory=dict, max_length=30)


def candidate_gate(candidate, location):
    blockers = []
    if candidate.kind not in {"single_event", "article"}:
        blockers.append({"code": "kind:" + candidate.kind, "message": candidate.kind})
    blockers.extend(
        {"code": f"ambiguity:{i}", "message": message}
        for i, message in enumerate(candidate.ambiguities)
    )
    if location.status == "ambiguous":
        blockers.append({"code": "location:ambiguous", "message": "地点存在多个候选"})
    return {
        "eligible_for_confirmation": not blockers,
        "review_required": True,
        "blocking_reasons": blockers,
        "missing_fields": [f for f in FIELDS if getattr(candidate, f) is None],
        "notices": candidate.notices,
        "location_resolution": location.model_dump(mode="json"),
    }


def job_gate(job, session):
    if job.status not in {"needs_review", "published"}:
        return {
            "eligible_for_confirmation": False,
            "review_required": True,
            "blocking_reasons": [
                {"code": "status:" + job.status, "message": job.error or job.status}
            ],
        }
    try:
        candidate = Candidate.model_validate(job.result["candidate"])
        item = validate_candidate(candidate, InformationInput.model_validate(job.source))
    except (ValueError, TypeError, KeyError):
        # Older successful snapshots can fail a newer validator; inspection must still work.
        return {
            "eligible_for_confirmation": False,
            "review_required": True,
            "blocking_reasons": [
                {
                    "code": "validation:invalid_saved_candidate",
                    "message": "历史候选不满足当前校验，请核对原文并重新处理",
                }
            ],
        }
    return candidate_gate(candidate, LocationResolver(session).resolve(item.activity_location))


def fingerprint(job):
    # Imported lazily to avoid a service/review cycle. Changes invalidate exported packets.
    from app.services.content.processing.service import digest

    return digest([str(job.id), job.version, job.source, job.result, job.status, job.attempts])
