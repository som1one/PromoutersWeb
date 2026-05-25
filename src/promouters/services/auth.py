from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.core.config import Settings
from promouters.integrations.sms_ru import SMSRuClient
from promouters.models.auth import LoginSMSCode
from promouters.models.enums import UserStatus
from promouters.models.users import User
from promouters.schemas.auth import LoginChallengeResponse, TokenPairResponse, UserPublic
from promouters.utils.jwt import create_jwt_token, create_refresh_jwt_token, decode_jwt_token
from promouters.utils.passwords import verify_password


def normalize_phone(phone: str) -> str:
    return "".join(char for char in phone if char.isdigit() or char == "+")


def get_user_by_phone(db: Session, phone: str) -> User | None:
    normalized_phone = normalize_phone(phone)
    stmt = (
        select(User)
        .options(joinedload(User.role), joinedload(User.branch))
        .where(User.phone == normalized_phone)
    )
    return db.scalar(stmt)


def authenticate_user(db: Session, phone: str, password: str) -> User:
    user = get_user_by_phone(db, phone)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone or password",
        )
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not active",
        )
    return user


def _generate_sms_code(code_length: int) -> str:
    min_value = 10 ** (code_length - 1)
    max_value = (10**code_length) - 1
    return str(secrets.randbelow(max_value - min_value + 1) + min_value)


def _hash_code(challenge_id: UUID, code: str) -> str:
    return hashlib.sha256(f"{challenge_id}:{code}".encode("utf-8")).hexdigest()


def to_user_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        first_name=user.first_name,
        last_name=user.last_name,
        middle_name=user.middle_name,
        status=user.status.value,
        role_id=user.role_id,
        role_code=user.role.code if user.role else None,
        branch_id=user.branch_id,
        role_name=user.role.name if user.role else None,
        branch_name=user.branch.name if user.branch else None,
        branch_city=user.branch.city if user.branch else None,
    )


def build_token_response(user: User, settings: Settings) -> TokenPairResponse:
    access_token = create_jwt_token(
        user_id=str(user.id),
        secret=settings.jwt_secret,
        expiration_time=settings.jwt_expiration_time,
        algorithm=settings.jwt_algorithm,
    )
    refresh_token = create_refresh_jwt_token(
        user_id=str(user.id),
        refresh_secret=settings.jwt_refresh_secret,
        refresh_expiration_time=settings.jwt_refresh_expiration_time,
        refresh_algorithm=settings.jwt_refresh_algorithm,
    )
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=to_user_public(user),
    )


def create_login_flow(
    db: Session,
    settings: Settings,
    phone: str,
    password: str,
) -> LoginChallengeResponse:
    user = authenticate_user(db, phone, password)

    if not settings.auth_sms_enabled:
        response = build_token_response(user, settings)
        user.last_login_at = datetime.now(UTC)
        db.add(user)
        db.commit()
        db.refresh(user)
        return LoginChallengeResponse(
            requires_sms_verification=False,
            access_token=response.access_token,
            refresh_token=response.refresh_token,
            token_type=response.token_type,
            user=response.user,
        )

    deactivate_existing_login_codes(db, user.id)
    if not user.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a phone number for SMS verification",
        )

    challenge = LoginSMSCode(
        user_id=user.id,
        phone=user.phone,
        code_hash="",
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.auth_sms_code_ttl_seconds),
    )
    db.add(challenge)
    db.flush()

    code = _generate_sms_code(settings.auth_sms_code_length)
    challenge.code_hash = _hash_code(challenge.id, code)
    db.add(challenge)

    try:
        sms_client = SMSRuClient(settings)
        sms_client.send_login_code(phone=challenge.phone, code=code)
    except Exception:
        db.rollback()
        raise

    db.commit()
    return LoginChallengeResponse(
        requires_sms_verification=True,
        challenge_id=challenge.id,
        expires_at=challenge.expires_at,
    )


def deactivate_existing_login_codes(db: Session, user_id: UUID) -> None:
    stmt = select(LoginSMSCode).where(
        LoginSMSCode.user_id == user_id,
        LoginSMSCode.is_active.is_(True),
        LoginSMSCode.used_at.is_(None),
    )
    for challenge in db.scalars(stmt):
        challenge.is_active = False
        db.add(challenge)
    db.flush()


def verify_login_code(
    db: Session,
    settings: Settings,
    challenge_id: UUID,
    code: str,
) -> TokenPairResponse:
    challenge = db.get(LoginSMSCode, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")
    if not challenge.is_active or challenge.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Challenge is no longer active")
    if challenge.expires_at < datetime.now(UTC):
        challenge.is_active = False
        db.add(challenge)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Challenge has expired")
    if challenge.invalid_attempts >= settings.auth_sms_max_attempts:
        challenge.is_active = False
        db.add(challenge)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many invalid attempts")

    expected_hash = _hash_code(challenge.id, code)
    if not secrets.compare_digest(expected_hash, challenge.code_hash):
        challenge.invalid_attempts += 1
        db.add(challenge)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    user = db.get(User, challenge.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    challenge.used_at = datetime.now(UTC)
    challenge.is_active = False
    user.last_login_at = datetime.now(UTC)
    db.add_all([challenge, user])
    db.commit()
    db.refresh(user)
    return build_token_response(user, settings)


def refresh_tokens(db: Session, settings: Settings, refresh_token: str) -> TokenPairResponse:
    payload = decode_jwt_token(
        token=refresh_token,
        secret=settings.jwt_refresh_secret,
        algorithm=settings.jwt_refresh_algorithm,
    )
    user_id = UUID(str(payload["user_id"]))
    user = db.scalar(select(User).options(joinedload(User.role), joinedload(User.branch)).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not active")
    return build_token_response(user, settings)
