from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from promouters.models.enums import UserStatus


class UserRead(BaseModel):
    id: UUID
    username: str
    email: str
    phone: str | None
    first_name: str
    last_name: str
    middle_name: str | None
    status: str
    is_superuser: bool
    last_login_at: datetime | None
    role_id: UUID
    role_code: str | None = None
    branch_id: UUID | None
    role_name: str | None = None
    branch_name: str | None = None
    branch_city: str | None = None
    city_id: int | None = None
    city_name: str | None = None
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: str = Field(min_length=5, max_length=255)
    phone: str | None = Field(default=None, min_length=5, max_length=32)
    password: str = Field(min_length=8, max_length=255)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    tg_id: int | None = None
    status: UserStatus = UserStatus.ACTIVE
    is_superuser: bool = False
    role_id: UUID
    branch_id: UUID | None = None
    city_id: int | None = None


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=64)
    email: str | None = Field(default=None, min_length=5, max_length=255)
    phone: str | None = Field(default=None, min_length=5, max_length=32)
    password: str | None = Field(default=None, min_length=8, max_length=255)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    tg_id: int | None = None
    status: UserStatus | None = None
    is_superuser: bool | None = None
    role_id: UUID | None = None
    branch_id: UUID | None = None
    city_id: int | None = None


class CurrentUserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=64)
    email: str | None = Field(default=None, min_length=5, max_length=255)
    phone: str | None = Field(default=None, min_length=5, max_length=32)
    password: str | None = Field(default=None, min_length=8, max_length=255)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)


class UserDeleteResponse(BaseModel):
    id: UUID
    message: str
