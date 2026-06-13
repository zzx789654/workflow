import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class OrgUnit(Base):
    """組織單位——自我參照鄰接表，支援任意多層（部門 > 課別 > …）。

    每個單位可指派一位主管（manager_user_id）；該主管自動可見此單位及其
    所有子單位成員的日曆（可視範圍解析見 app/core/visibility.py）。
    """

    __tablename__ = "org_units"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # parent_id 為 None 即為頂層單位；SET NULL 讓刪父單位不孤兒化子單位（升為頂層）
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("org_units.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # 主管使用者；SET NULL 讓刪除使用者不連帶毀損單位。
    # users 與 org_units 互相參照（users.org_unit_id ↔ org_units.manager_user_id）形成 FK 環，
    # use_alter + 具名約束讓 SQLAlchemy 能以獨立 ALTER 建立/卸除，化解 create/drop 排序循環。
    manager_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True, name="fk_org_units_manager_user_id"),
        nullable=True,
        index=True,
    )
    # 來源：manual（手動建立，預設）/ ad（AD/OU 同步而來）。同步只碰 ad，永不動 manual。
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    # ad 來源存該 OU 的 DN（穩定鍵，冪等對應）；manual 為 None。
    external_id: Mapped[str | None] = mapped_column(String(1000), nullable=True, index=True)
    # AD 中 OU 消失時標 False（保留可人工複核，不硬刪、不孤兒化使用者）。
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    parent: Mapped["OrgUnit | None"] = relationship("OrgUnit", remote_side="OrgUnit.id", back_populates="children")
    # 不做 ORM cascade delete：刪父單位時子單位應由 DB 的 ondelete=SET NULL 升為頂層，
    # 而非被連帶刪除。passive_deletes 讓 ORM 不主動載入子列、交給 DB FK 處理。
    children: Mapped[list["OrgUnit"]] = relationship("OrgUnit", back_populates="parent", passive_deletes=True)
    manager: Mapped["User | None"] = relationship("User", foreign_keys=[manager_user_id])
    members: Mapped[list["User"]] = relationship("User", back_populates="org_unit", foreign_keys="User.org_unit_id")


class UserCalendarGrant(Base):
    """admin 額外授權：讓某使用者（通常是主管）可額外檢視某 org_unit（含子樹）的日曆。

    可視範圍 = 自管單位子樹（OrgUnit.manager_user_id）∪ 此授權單位子樹。
    """

    __tablename__ = "user_calendar_grants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    org_unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("org_units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    org_unit: Mapped["OrgUnit"] = relationship("OrgUnit")
