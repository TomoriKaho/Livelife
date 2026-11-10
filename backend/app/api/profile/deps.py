"""身份依赖：复用账户模块的真实会话校验。"""

from uuid import UUID

from fastapi import Depends

from app.api.accounts.router import get_current_user
from app.db.models.accounts import User


def get_current_user_id(user: User = Depends(get_current_user)) -> UUID:
    """返回当前登录用户标识，供资料与兴趣读写使用。"""

    return user.id
