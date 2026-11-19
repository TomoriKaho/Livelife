from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base
from app.db.types import UTCDateTime
from app.db.vector import Embedding


class RetrievalState(Base):
    __tablename__ = "information_retrieval_state"
    __table_args__ = (Index("ix_retrieval_retry", "retry_at", "information_id"),)

    information_id: Mapped[UUID] = mapped_column(
        ForeignKey("information_items.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(BigInteger, server_default=text("1"))
    indexed_revision: Mapped[int | None] = mapped_column(BigInteger)
    profile: Mapped[str | None] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    retry_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_error: Mapped[str | None] = mapped_column(String(64))


class RetrievalChunk(Base):
    __tablename__ = "information_retrieval_chunks"
    __table_args__ = (Index("ix_retrieval_profile", "profile", "information_id"),)

    information_id: Mapped[UUID] = mapped_column(
        ForeignKey("information_items.id", ondelete="CASCADE"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(BigInteger)
    profile: Mapped[str] = mapped_column(String(64))
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Embedding())
