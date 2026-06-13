import uuid

from pydantic import BaseModel, Field


class OrgUnitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: uuid.UUID | None = None
    manager_user_id: uuid.UUID | None = None


class OrgUnitUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    parent_id: uuid.UUID | None = None
    manager_user_id: uuid.UUID | None = None


class OrgUnitOut(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    manager_user_id: uuid.UUID | None
    source: str = "manual"
    is_active: bool = True

    model_config = {"from_attributes": True}


class AdSyncResult(BaseModel):
    created: int
    updated: int
    deactivated: int
    members_assigned: int
    users_created: int = 0
    users_updated: int = 0
    users_deactivated: int = 0
    message: str


class CalendarGrantCreate(BaseModel):
    org_unit_id: uuid.UUID


class CalendarGrantOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    org_unit_id: uuid.UUID

    model_config = {"from_attributes": True}
