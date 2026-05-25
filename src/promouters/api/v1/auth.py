from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from promouters.api.deps import get_current_user
from promouters.core.config import Settings, get_settings
from promouters.db.session import get_db
from promouters.models.users import User
from promouters.schemas.auth import (
    LoginChallengeResponse,
    LoginRequest,
    RefreshTokenRequest,
    TokenPairResponse,
    UserPublic,
    VerifyLoginCodeRequest,
)
from promouters.services.audit import write_audit_log
from promouters.services.auth import (
    create_login_flow,
    get_user_by_phone,
    refresh_tokens,
    to_user_public,
    verify_login_code,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginChallengeResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LoginChallengeResponse:
    try:
        response = create_login_flow(db=db, settings=settings, phone=payload.phone, password=payload.password)
    except HTTPException as exc:
        write_audit_log(
            db,
            actor_user=None,
            branch_id=None,
            entity_type="auth",
            entity_id=None,
            action="auth.login.failed",
            payload={"phone": payload.phone, "result": "failed", "detail": exc.detail},
            request=request,
            commit=True,
        )
        raise

    actor_user = get_user_by_phone(db, payload.phone)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=actor_user.branch_id if actor_user else None,
        entity_type="auth",
        entity_id=str(actor_user.id) if actor_user else None,
        action="auth.login.challenge_issued" if response.requires_sms_verification else "auth.login.success",
        payload={
            "phone": payload.phone,
            "result": "challenge" if response.requires_sms_verification else "success",
            "requires_sms_verification": response.requires_sms_verification,
        },
        request=request,
        commit=True,
    )
    return response


@router.post("/verify-sms", response_model=TokenPairResponse)
def verify_sms_code(
    payload: VerifyLoginCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenPairResponse:
    try:
        response = verify_login_code(
            db=db,
            settings=settings,
            challenge_id=payload.challenge_id,
            code=payload.code,
        )
    except HTTPException as exc:
        write_audit_log(
            db,
            actor_user=None,
            branch_id=None,
            entity_type="auth",
            entity_id=str(payload.challenge_id),
            action="auth.verify_sms.failed",
            payload={"challenge_id": str(payload.challenge_id), "result": "failed", "detail": exc.detail},
            request=request,
            commit=True,
        )
        raise

    actor_user = db.get(User, response.user.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=actor_user.branch_id if actor_user else None,
        entity_type="auth",
        entity_id=str(response.user.id),
        action="auth.verify_sms.success",
        payload={"challenge_id": str(payload.challenge_id), "result": "success"},
        request=request,
        commit=True,
    )
    return response


@router.post("/refresh", response_model=TokenPairResponse)
def refresh(
    payload: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenPairResponse:
    try:
        response = refresh_tokens(db=db, settings=settings, refresh_token=payload.refresh_token)
    except HTTPException as exc:
        write_audit_log(
            db,
            actor_user=None,
            branch_id=None,
            entity_type="auth",
            entity_id=None,
            action="auth.refresh.failed",
            payload={"result": "failed", "detail": exc.detail},
            request=request,
            commit=True,
        )
        raise

    actor_user = db.get(User, response.user.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=actor_user.branch_id if actor_user else None,
        entity_type="auth",
        entity_id=str(response.user.id),
        action="auth.refresh.success",
        payload={"result": "success"},
        request=request,
        commit=True,
    )
    return response


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)) -> UserPublic:
    return to_user_public(current_user)
