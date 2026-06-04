import logging
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.core.security import decode_token
from app.db.session import get_db
from app.models.project import ProjectMember, ProjectRole
from app.models.user import User, UserRole

bearer = HTTPBearer()

# 專案角色排序（由低到高）
_PROJECT_ROLE_ORDER = [ProjectRole.viewer, ProjectRole.member, ProjectRole.manager, ProjectRole.owner]


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    user_id = decode_token(token)
    if not user_id:
        logger.warning("Auth failed: invalid token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        logger.warning("Auth failed: malformed user_id in token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == uid, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


async def get_project_role(
    project_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> ProjectRole | None:
    """回傳使用者在此專案的角色；系統 admin 視為 owner；非成員回傳 None。"""
    if user.role == UserRole.admin:
        return ProjectRole.owner
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
    )
    membership = result.scalar_one_or_none()
    return membership.role if membership else None


async def require_project_membership(
    project_id: uuid.UUID,
    user: User,
    db: AsyncSession,
    min_role: ProjectRole = ProjectRole.viewer,
) -> ProjectRole:
    """
    確認使用者在此專案有 min_role 以上的角色。
    - viewer  : 可讀取
    - member  : 可新增/修改任務、留言
    - manager : 可管理成員、自訂欄位、刪除任務
    - owner   : 完整控制（含刪除專案）
    系統 admin 恆通過（視為 owner）。
    """
    role = await get_project_role(project_id, user, db)
    if role is None:
        raise HTTPException(status_code=403, detail="你不是此專案的成員")
    if _PROJECT_ROLE_ORDER.index(role) < _PROJECT_ROLE_ORDER.index(min_role):
        role_labels = {
            ProjectRole.viewer:  "檢視者",
            ProjectRole.member:  "成員",
            ProjectRole.manager: "管理者",
            ProjectRole.owner:   "擁有者",
        }
        raise HTTPException(
            status_code=403,
            detail=f"需要 {role_labels[min_role]} 以上角色，你目前是 {role_labels[role]}",
        )
    return role
