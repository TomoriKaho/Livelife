from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.repositories.sql.information import InformationRepository
from app.schemas.information import Information, InformationInput

MAX_BATCH_SIZE = 1000


class InformationAggregator:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = InformationRepository(session)

    def ingest(self, records: Iterable[InformationInput]) -> tuple[Information, ...]:
        """Validate a bounded batch, then persist it atomically in a fresh Session."""
        batch: list[InformationInput] = []
        for record in records:
            if len(batch) >= MAX_BATCH_SIZE:
                raise ValueError(f"a batch may contain at most {MAX_BATCH_SIZE} records")
            batch.append(InformationInput.model_validate(record))
        if not batch:
            return ()

        processed_at = datetime.now(UTC)
        with self.session.begin():
            for item in batch:
                self.repository.upsert(item, processed_at)
            # Multiple observations of a source within a batch return its final snapshot once.
            identities = dict.fromkeys((item.platform, item.source_id) for item in batch)
            result = tuple(
                Information.model_validate(self.repository.get_by_source(platform, source_id))
                for platform, source_id in identities
            )
        return result
