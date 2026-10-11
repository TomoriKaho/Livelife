"""ORM 模型包；新增业务模型后在此导入，供 Alembic 收集完整 metadata。"""

from app.db.models.base import Base
from app.db.models.information import InformationRecord

__all__ = ["Base", "InformationRecord"]
