"""Bounded, explicit one-pass execution, never an automatic retry loop."""

import asyncio
import time
from uuid import UUID

from app.services.content.processing.service import ProcessingError


async def run_batch(service, job_ids, *, retry_failed=False, on_result=None):
    ids = list(dict.fromkeys(UUID(str(item)) for item in job_ids))
    if not 1 <= len(ids) <= 100:
        raise ProcessingError("batch_requires_1_to_100_jobs")
    # Validate the entire manifest before making any model calls.
    for job_id in ids:
        service.get(job_id)
    results = []
    last_start = None
    for job_id in ids:
        before = service.get(job_id)
        eligible = before["status"] == ("failed" if retry_failed else "pending")
        blocked = None
        if eligible:
            if last_start is not None:
                await asyncio.sleep(
                    max(
                        0,
                        60 / service.model.limits.requests_per_minute
                        + 1
                        - (time.monotonic() - last_start),
                    )
                )
            last_start = time.monotonic()
            try:
                await service.process(job_id, retry=retry_failed)
            except ProcessingError as exc:
                blocked = str(exc)
        result = service.get(job_id)
        result["batch_action"] = "attempted" if eligible else "reused_or_skipped"
        result["batch_error"] = blocked
        results.append(result)
        if on_result:
            on_result(results)
    return results
