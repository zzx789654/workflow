import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    member = "member"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # username 是登入鍵（全域唯一）；email 改為可空、非唯一的聯絡資訊
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(254), index=True, nullable=True)
    # 帳號來源：local（本地密碼）/ ldap / radius（遠端驗證，自動建立）
    auth_source: Mapped[str] = mapped_column(String(20), default="local", nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, create_type=False), default=UserRole.member, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 組織歸屬：所屬單位（部門/課別葉節點）與職位文字。僅 admin 可改（防越權竄改歸屬）。
    org_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("org_units.id", ondelete="SET NULL", use_alter=True, name="fk_users_org_unit_id"),
        nullable=True,
        index=True,
    )
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # AD 使用者的 DN（同步帶入，供「有 DN 自動歸 OU」判斷）；local 帳號為 None。
    external_id: Mapped[str | None] = mapped_column(String(1000), nullable=True, index=True)
    auto_archive_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 提高此值即令該使用者所有既發 token 失效（改密碼/登出時 +1）
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    project_memberships: Mapped[list["ProjectMember"]] = relationship(back_populates="user")
    assigned_tasks: Mapped[list["TaskAssignee"]] = relationship(back_populates="user")
    comments: Mapped[list["TaskComment"]] = relationship(back_populates="author")
    daily_tasks: Mapped[list["DailyTask"]] = relationship(back_populates="user")
    org_unit: Mapped["OrgUnit | None"] = relationship("OrgUnit", back_populates="members", foreign_keys=[org_unit_id])
