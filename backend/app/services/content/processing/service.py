"""Explicit system jobs with persistent lease, retry accounting and reviewed publication."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.db.models import InformationRecord, ProcessingAttempt, ProcessingGate, ProcessingJob
from app.schemas.information import InformationInput
from app.services.content.locations import LocationResolver
from app.services.content.processing.model import ExtractionModel, ModelFailure
from app.services.content.processing.review import (
    FallbackInput,
    candidate_gate,
    fingerprint,
    job_gate,
)
from app.services.content.processing.schemas import (
    FIELDS,
    Candidate,
    EvidenceError,
    validate_candidate,
)
from app.services.content.processing.selection import convert_selection


class ProcessingError(RuntimeError):
    pass


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def snapshot(job):
    return {
        key: getattr(job, key)
        for key in (
            "id",
            "status",
            "content_hash",
            "version",
            "model",
            "attempts",
            "error",
            "source",
            "result",
            "created_at",
            "updated_at",
            "review",
        )
    }


def diagnosis(job, model):
    detail = (job.result or {}).get("validation_error")
    if job.error in {
        "model_unavailable",
        "model_timeout",
        "model_rate_limited",
        "interrupted",
        "lease_expired",
    }:
        category, action = "provider", "check_provider_then_retry"
    elif job.error in {"budget_exhausted", "rate_limited"}:
        category, action = "quota", "wait_for_window_or_adjust_limit"
    elif job.error == "model_not_configured":
        category, action = "configuration", "configure_model_then_retry"
    elif job.error == "input_too_large":
        category, action = "input", "review_input_and_submit_again"
    elif job.error == "attempt_limit":
        category, action = "limit", "manual_review_required"
    elif job.error:
        category, action = "extraction", "inspect_attempt_evidence_before_explicit_retry"
    elif job.status == "running":
        category, action = "running", "wait_for_completion_or_expired_lease_then_run"
    elif job.status == "needs_review":
        category, action = "review", "review_candidate_and_missing_fields"
    else:
        category, action = job.status, "none"
    same_version = job.key == digest([job.content_hash, model.identity, model.version])
    if job.status == "failed" and job.attempts >= model.limits.max_attempts:
        action = "manual_review_required"
    if not same_version and job.status == "failed":
        action = "submit_original_with_current_version"
    return {
        "category": category,
        "error": job.error,
        "validation_error": detail,
        "next_action": action,
        "current_model_version_matches": same_version,
        "attempts_remaining": max(0, model.limits.max_attempts - job.attempts),
        "requires_explicit_retry": job.status == "failed",
    }


class Processor:
    def __init__(self, sessions, model=None):
        self.sessions = sessions
        self.model = model or ExtractionModel()

    def submit(self, source: InformationInput):
        # Raw adapter metadata is not model input. No inferred activity fields are trusted here.
        source = InformationInput.model_validate(source.model_dump())
        data = source.model_dump(mode="json")
        for field in (*FIELDS, "place_id"):
            data[field] = None
        data["raw_payload"] = {}
        stable = {k: v for k, v in data.items() if k != "fetched_at"}
        content_hash = digest(stable)
        key = digest([content_hash, self.model.identity, self.model.version])
        now = datetime.now(UTC)
        with self.sessions() as s:
            job = s.scalar(select(ProcessingJob).where(ProcessingJob.key == key))
            if job:
                return job.id
            job = ProcessingJob(
                id=uuid4(),
                key=key,
                content_hash=content_hash,
                version=self.model.version,
                model=self.model.name,
                status="pending",
                source=data,
                attempts=0,
                created_at=now,
                updated_at=now,
            )
            s.add(job)
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                return s.scalar(select(ProcessingJob.id).where(ProcessingJob.key == key))
            return job.id

    def get(self, job_id):
        with self.sessions() as s:
            job = s.get(ProcessingJob, job_id)
            if not job:
                raise ProcessingError("job_not_found")
            result = snapshot(job)
            result["attempt_log"] = [
                {
                    "id": a.id,
                    "started_at": a.started_at,
                    "reserved_tokens": a.reserved_tokens,
                    "usage": a.usage,
                    "error": a.error,
                    "diagnostics": a.diagnostics,
                }
                for a in s.scalars(
                    select(ProcessingAttempt)
                    .where(ProcessingAttempt.job_id == job_id)
                    .order_by(ProcessingAttempt.started_at)
                )
            ]
            result["diagnosis"] = diagnosis(job, self.model)
            result["review_gate"] = job_gate(job, s)
            return result

    def list_jobs(self, *, status=None, version=None, limit=50, offset=0):
        if status not in {None, "pending", "running", "failed", "needs_review", "published"}:
            raise ProcessingError("invalid_status")
        if not 1 <= limit <= 100 or offset < 0:
            raise ProcessingError("invalid_pagination")
        with self.sessions() as s:
            query = select(ProcessingJob)
            if status:
                query = query.where(ProcessingJob.status == status)
            if version:
                query = query.where(ProcessingJob.version == version)
            query = (
                query.order_by(ProcessingJob.updated_at.desc(), ProcessingJob.id)
                .offset(offset)
                .limit(limit)
            )
            return [
                {
                    "job_id": j.id,
                    "title": j.source.get("title"),
                    "source_id": j.source["source_id"],
                    "source_name": j.source.get("source_name"),
                    "status": j.status,
                    "version": j.version,
                    "attempts": j.attempts,
                    "updated_at": j.updated_at,
                    "diagnosis": diagnosis(j, self.model),
                }
                for j in s.scalars(query)
            ]

    def export_fallback(self, job_id):
        with self.sessions() as s:
            job = s.get(ProcessingJob, job_id)
            if not job:
                raise ProcessingError("job_not_found")
            if job.status not in {"failed", "needs_review"}:
                raise ProcessingError("job_not_fallback_ready")
            gate = job_gate(job, s)
            return {
                "source_job_id": str(job.id),
                "source_fingerprint": fingerprint(job),
                "selection": (job.result or {}).get("selection"),
                "resolutions": {r["code"]: "" for r in gate["blocking_reasons"]},
            }

    def manual_fallback(self, packet, *, reviewed_by, reason):
        packet = FallbackInput.model_validate(packet)
        if not reviewed_by.strip() or not reason.strip():
            raise ProcessingError("review_required")
        with self.sessions.begin() as s:
            # A no-op write serializes fallback/retry/publication on SQLite and PostgreSQL.
            s.execute(
                update(ProcessingJob)
                .where(ProcessingJob.id == packet.source_job_id)
                .values(updated_at=ProcessingJob.updated_at)
            )
            parent = s.get(ProcessingJob, packet.source_job_id)
            if not parent:
                raise ProcessingError("job_not_found")
            if parent.status not in {"failed", "needs_review"}:
                raise ProcessingError("job_not_fallback_ready")
            if fingerprint(parent) != packet.source_fingerprint:
                raise ProcessingError("stale_review_packet_export_again")
            gate = job_gate(parent, s)
            required = {r["code"] for r in gate["blocking_reasons"]}
            if set(packet.resolutions) != required or any(
                not value.strip() or len(value) > 2000 for value in packet.resolutions.values()
            ):
                raise ProcessingError("explain_each_blocking_reason")
            previous = (
                (parent.result or {}).get("candidate")
                or (parent.result or {}).get("selection")
                or {}
            )
            if previous.get("kind") == "multiple_events":
                raise ProcessingError("multiple_events_require_separate_split_workflow")
            source = InformationInput.model_validate(parent.source)
            candidate = convert_selection(packet.selection, source)
            proposed = validate_candidate(candidate, source)
            location = LocationResolver(s).resolve(proposed.activity_location)
            if not candidate_gate(candidate, location)["eligible_for_confirmation"]:
                raise ProcessingError("manual_candidate_still_blocked")
            provenance = {
                "source_job_id": str(parent.id),
                "source_fingerprint": packet.source_fingerprint,
                "reviewed_by": reviewed_by.strip(),
                "reason": reason.strip(),
                "resolutions": packet.resolutions,
            }
            key = digest(
                ["manual-fallback-v1", provenance, packet.selection.model_dump(mode="json")]
            )
            existing = s.scalar(select(ProcessingJob).where(ProcessingJob.key == key))
            if existing:
                return existing.id
            now = datetime.now(UTC)
            job = ProcessingJob(
                id=uuid4(),
                key=key,
                content_hash=parent.content_hash,
                version="manual-fallback-v1",
                model="human",
                status="needs_review",
                attempts=0,
                source=parent.source,
                created_at=now,
                updated_at=now,
                result={
                    "candidate": candidate.model_dump(mode="json"),
                    "selection": packet.selection.model_dump(mode="json"),
                    "proposed": proposed.model_dump(mode="json"),
                    "missing_fields": [f for f in FIELDS if getattr(candidate, f) is None],
                    "location_resolution": location.model_dump(mode="json"),
                    "review_required": True,
                    "manual_review": {**provenance, "reviewed_at": now.isoformat()},
                },
            )
            s.add(job)
            # The parent row lock serializes concurrent fallback submissions on PostgreSQL.
            s.flush()
            return job.id

    async def retry_failed(self, job_id):
        if self.get(job_id)["status"] != "failed":
            raise ProcessingError("retry_requires_failed_job")
        return await self.process(job_id, retry=True)

    async def process(self, job_id, *, retry=False):
        owner = uuid4()
        now = datetime.now(UTC)
        limits = self.model.limits
        with self.sessions.begin() as s:
            # One execution at a time for this explicit CLI. No in-memory-only quota/lock.
            gate = s.execute(
                update(ProcessingGate)
                .where(ProcessingGate.id == 1, ProcessingGate.lease_until <= now)
                .values(owner=owner, lease_until=now + timedelta(seconds=self.model.timeout + 30))
            )
            if gate.rowcount != 1:
                raise ProcessingError("processor_busy")
            job = s.get(ProcessingJob, job_id)
            if not job:
                raise ProcessingError("job_not_found")
            if job.status in {"needs_review", "published"}:
                s.execute(update(ProcessingGate).values(owner=None, lease_until=now))
                return snapshot(job)
            if job.status == "failed" and not retry:
                s.execute(update(ProcessingGate).values(owner=None, lease_until=now))
                return snapshot(job)
            if (
                job.model != self.model.name
                or job.version != self.model.version
                or job.key != digest([job.content_hash, self.model.identity, self.model.version])
            ):
                raise ProcessingError("model_version_mismatch_submit_again")
            source = InformationInput.model_validate(job.source)
            error = None
            if not self.model.configured:
                error = "model_not_configured"
            elif len(source.content) > limits.max_chars:
                error = "input_too_large"
            elif job.attempts >= limits.max_attempts:
                error = "attempt_limit"
            reservation = self.model.reservation(source)
            spent = s.scalar(
                select(func.coalesce(func.sum(ProcessingAttempt.reserved_tokens), 0)).where(
                    ProcessingAttempt.started_at >= now - timedelta(hours=24)
                )
            )
            recent = s.scalar(
                select(func.count())
                .select_from(ProcessingAttempt)
                .where(ProcessingAttempt.started_at >= now - timedelta(minutes=1))
            )
            if not error and spent + reservation > limits.daily_tokens:
                error = "budget_exhausted"
            if not error and recent >= limits.requests_per_minute:
                error = "rate_limited"
            if error:
                job.status, job.error, job.updated_at = "failed", error, now
                s.execute(update(ProcessingGate).values(owner=None, lease_until=now))
                return snapshot(job)
            if job.status == "running":
                # An expired lease means the old execution cannot commit any late result.
                s.execute(
                    update(ProcessingAttempt)
                    .where(
                        ProcessingAttempt.job_id == job_id,
                        ProcessingAttempt.error.is_(None),
                        ProcessingAttempt.usage.is_(None),
                    )
                    .values(error="lease_expired")
                )
            attempt_id = uuid4()
            s.add(
                ProcessingAttempt(
                    id=attempt_id, job_id=job_id, started_at=now, reserved_tokens=reservation
                )
            )
            job.status, job.error = "running", None
            job.attempts += 1
            job.updated_at = now
        result = usage = candidate = selection = None
        phase = "model_request"
        validation_error = None
        structure_errors = []
        error = None
        cancelled = False
        try:
            output, usage = await asyncio.wait_for(self.model.extract(source), self.model.timeout)
            phase = "parse_output"
            if getattr(self.model, "selects_spans", False):
                from app.services.content.processing.selection import Selection, convert_selection

                selection = Selection.model_validate_json(output)
                phase = "convert_selection"
                candidate = convert_selection(selection, source)
            else:
                candidate = Candidate.model_validate_json(output)
            phase = "validate_evidence"
            proposed = validate_candidate(candidate, source)
            phase = "resolve_location"
            with self.sessions() as s:
                location = LocationResolver(s).resolve(proposed.activity_location)
            result = {
                "candidate": candidate.model_dump(mode="json"),
                "selection": selection.model_dump(mode="json") if selection else None,
                "proposed": proposed.model_dump(mode="json"),
                "missing_fields": [f for f in FIELDS if getattr(candidate, f) is None],
                "location_resolution": location.model_dump(mode="json"),
                "review_required": True,
            }
        except ModelFailure as exc:
            error, usage = str(exc), exc.usage
        except TimeoutError:
            error = "model_timeout"
        except asyncio.CancelledError:
            error, cancelled = "interrupted", True
        except (ValueError, TypeError) as exc:
            error = "invalid_output_or_evidence"
            validation_error = str(exc) if isinstance(exc, EvidenceError) else "invalid_structure"
            if isinstance(exc, ValidationError):
                # Never save raw invalid output, input values, arbitrary messages or ctx.
                allowed = set(Candidate.model_fields) | {"quote", "value"}
                structure_errors = [
                    {
                        "field": ".".join(
                            str(p) if isinstance(p, int) or p in allowed else "unknown"
                            for p in e["loc"]
                        ),
                        "type": e["type"],
                    }
                    for e in exc.errors(include_url=False)[:20]
                ]
            result = {
                "candidate": candidate.model_dump(mode="json") if candidate else None,
                "selection": selection.model_dump(mode="json") if selection else None,
                "validation_error": validation_error,
                "review_required": True,
            }
        except Exception:
            # Do not persist upstream messages, URLs containing keys, or raw malformed output.
            error = "processing_failed"
        with self.sessions.begin() as s:
            now = datetime.now(UTC)
            gate = s.execute(
                update(ProcessingGate)
                .where(
                    ProcessingGate.id == 1,
                    ProcessingGate.owner == owner,
                    ProcessingGate.lease_until > now,
                )
                .values(owner=None, lease_until=now)
            )
            if gate.rowcount != 1:
                raise ProcessingError("lease_lost")
            attempt = s.get(ProcessingAttempt, attempt_id)
            attempt.usage, attempt.error = usage, error
            attempt.diagnostics = {
                "phase": phase,
                "error": error,
                "validation_error": validation_error,
                "structure_errors": structure_errors,
                "result": result,
            }
            job = s.get(ProcessingJob, job_id)
            job.status = "failed" if error else "needs_review"
            job.result, job.error, job.updated_at = result, error, now
            outcome = snapshot(job)
        if cancelled:
            raise asyncio.CancelledError
        return outcome

    def publish(self, job_id, *, reviewed_by, reason):
        """Trusted operator only; insert-only. Updates/corrections are deferred to #110."""
        if not reviewed_by.strip() or not reason.strip():
            raise ProcessingError("review_required")
        try:
            with self.sessions.begin() as s:
                # Conditional write serializes publication on SQLite and PostgreSQL.
                locked = s.execute(
                    update(ProcessingJob)
                    .where(ProcessingJob.id == job_id, ProcessingJob.status == "needs_review")
                    .values(updated_at=datetime.now(UTC))
                )
                job = s.get(ProcessingJob, job_id)
                if job and job.status == "published":
                    return UUID(job.review["information_id"])
                if locked.rowcount != 1:
                    raise ProcessingError("job_not_reviewable")
                candidate = Candidate.model_validate(job.result["candidate"])
                if candidate.kind not in {"single_event", "article"} or candidate.ambiguities:
                    raise ProcessingError("unresolved_candidate")
                item = validate_candidate(candidate, InformationInput.model_validate(job.source))
                resolution = LocationResolver(s).resolve(item.activity_location)
                if resolution.status == "ambiguous":
                    raise ProcessingError("ambiguous_location")
                values = item.model_dump(exclude={"source_url", "raw_payload"})
                information_id = uuid4()
                now = datetime.now(UTC)
                values.update(
                    id=information_id,
                    source_url=str(item.source_url) if item.source_url else None,
                    content=item.content.strip(),
                    raw_content=item.content,
                    raw_payload={
                        "processing_job_id": str(job.id),
                        "processing_version": job.version,
                    },
                    first_fetched_at=item.fetched_at,
                    processed_at=now,
                    place_id=resolution.place_id,
                    location_resolution=resolution.model_dump(mode="json"),
                )
                s.add(InformationRecord(**values))
                s.flush()  # Unique source constraint rejects overwriting any existing record.
                job.status = "published"
                job.review = {
                    "reviewed_by": reviewed_by,
                    "reason": reason,
                    "reviewed_at": now.isoformat(),
                    "information_id": str(information_id),
                }
                return information_id
        except IntegrityError as exc:
            raise ProcessingError("existing_source_requires_separate_review") from exc
