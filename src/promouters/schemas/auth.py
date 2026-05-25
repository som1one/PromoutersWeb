from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserPublic(BaseModel):
    id: UUID
    username: str
    email: str
    phone: str | None
    first_name: str
    last_name: str
    middle_name: str | None
    status: str
    role_id: UUID
    role_code: str | None = None
    branch_id: UUID | None
    role_name: str | None = None
    branch_name: str | None = None
    branch_city: str | None = None


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic


class LoginRequest(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    password: str = Field(min_length=1, max_length=255)


class LoginChallengeResponse(BaseModel):
    requires_sms_verification: bool
    challenge_id: UUID | None = None
    expires_at: datetime | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
    user: UserPublic | None = None


class VerifyLoginCodeRequest(BaseModel):
    challenge_id: UUID
    code: str = Field(min_length=4, max_length=10)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)
