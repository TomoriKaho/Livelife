"""ORM 模型包；新增业务模型后在此导入，供 Alembic 收集完整 metadata。"""

from app.db.models.accounts import EmailVerificationCode, User, UserSession
from app.db.models.agent import AgentIpWindow, AgentMessage, AgentSession, AgentUserUsage
from app.db.models.base import Base
from app.db.models.favorite import ActivityFavorite
from app.db.models.feedback import FeedbackEvent, UserFeedback
from app.db.models.information import InformationRecord, MapPlaceRecord, PlaceAliasRecord
from app.db.models.processing import ProcessingAttempt, ProcessingGate, ProcessingJob
from app.db.models.profile import UserInterest, UserProfile
from app.db.models.retrieval import RetrievalChunk, RetrievalState

__all__ = [
    "ActivityFavorite",
    "AgentIpWindow",
    "AgentMessage",
    "AgentSession",
    "AgentUserUsage",
    "Base",
    "FeedbackEvent",
    "UserFeedback",
    "ProcessingAttempt",
    "ProcessingGate",
    "ProcessingJob",
    "EmailVerificationCode",
    "InformationRecord",
    "MapPlaceRecord",
    "PlaceAliasRecord",
    "RetrievalChunk",
    "RetrievalState",
    "User",
    "UserInterest",
    "UserProfile",
    "UserSession",
]
