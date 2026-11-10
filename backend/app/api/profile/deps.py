"""身份依赖（临时）。

本文件是 #66 在账户系统合并前的替换接缝：main 上还没有 users / user_sessions 表，
因此这里用 Bearer 令牌的摘要派生稳定 UUID，仅用于让路由、契约与前端调用保持稳定。
#65（PR #68）合入 main 后只改本文件：
1. 改为 `from app.api.accounts.router import get_current_user`；
2. get_current_user_id 改为包装它并返回用户标识：
   `def get_current_user_id(user=Depends(get_current_user)) -> UUID: return user.id`；
3. 同时把迁移中 user_profiles.user_id 的外键补到 users.id。
路由、schema、契约和前端调用都不需要改动。

在完成替换前，本实现不提供真实身份校验，不得用于正式环境。
"""

import hashlib
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> UUID:
    token = credentials.credentials.strip() if credentials is not None else ""
    if credentials is None or credentials.scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    digest = hashlib.sha256(token.encode()).digest()
    return UUID(bytes=digest[:16], version=4)
