from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base
from app.db.types import UTCDateTime


class UserProfile(Base):
    """用户公开资料；主键与账户系统的用户标识一致。"""

    __tablename__ = "user_profiles"

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String(32))
    bio: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class UserInterest(Base):
    """用户勾选的兴趣标签，整体替换式写入。"""

    __tablename__ = "user_interests"

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("user_profiles.user_id", ondelete="CASCADE"), primary_key=True
    )
    tag: Mapped[str] = mapped_column(String(32), primary_key=True)
