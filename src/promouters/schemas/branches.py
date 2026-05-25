from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BranchRead(BaseModel):
    id: UUID
    name: str
    code: str | None
    city: str | None
    address: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=64)
    city: str | None = Field(default=None, max_length=128)
    address: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=64)
    city: str | None = Field(default=None, max_length=128)
    address: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class BranchDeleteResponse(BaseModel):
    id: UUID
    message: str
