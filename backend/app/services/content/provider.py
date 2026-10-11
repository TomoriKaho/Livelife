from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.sql.information import InformationRepository
from app.schemas.information import Information, InformationQuery


class InformationProvider:
    def __init__(self, session: Session) -> None:
        self.repository = InformationRepository(session)

    def get(self, information_id: UUID) -> Information | None:
        record = self.repository.get(information_id)
        return Information.model_validate(record) if record is not None else None

    def list(self, query: InformationQuery | None = None) -> tuple[Information, ...]:
        return tuple(
            Information.model_validate(record)
            for record in self.repository.list(query or InformationQuery())
        )
