from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from promouters.models.enums import RoleCode, UserStatus
from promouters.models.users import Branch, Role, User
from promouters.schemas.users import CurrentUserUpdate, UserCreate, UserRead, UserUpdate
from promouters.services.access import (
    can_assign_role,
    can_manage_user,
    ensure_same_branch,
    get_role_code,
    is_branch_manager,
    is_owner,
    require_branch_assignment,
)
from promouters.services.audit import write_audit_log
from promouters.services.auth import normalize_phone
from promouters.services.notifications import notify_owners_about_key_change
from promouters.utils.passwords import hash_password


def user_query() -> Select[tuple[User]]:
    return select(User).options(joinedload(User.role), joinedload(User.branch))


def to_user_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        first_name=user.first_name,
        last_name=user.last_name,
        middle_name=user.middle_name,
        status=user.status.value,
        is_superuser=user.is_superuser,
        last_login_at=user.last_login_at,
        role_id=user.role_id,
        role_code=user.role.code if user.role else None,
        branch_id=user.branch_id,
        role_name=user.role.name if user.role else None,
        branch_name=user.branch.name if user.branch else None,
        branch_city=user.branch.city if user.branch else None,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def serialize_user_for_audit(user: User) -> dict:
    return to_user_read(user).model_dump(mode="json")


def get_user_or_404(db: Session, user_id: UUID) -> User:
    user = db.scalar(user_query().where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def get_role_or_404(db: Session, role_id: UUID) -> Role:
    role = db.scalar(select(Role).where(Role.id == role_id, Role.is_system.is_(True)))
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


def _ensure_branch_exists(db: Session, branch_id: UUID | None) -> None:
    if branch_id is not None and db.get(Branch, branch_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")


def _ensure_unique_fields(
    db: Session,
    *,
    username: str | None,
    email: str | None,
    phone: str | None,
    exclude_user_id: UUID | None = None,
) -> str | None:
    normalized_phone = normalize_phone(phone) if phone else None
    stmt = user_query()

    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)

    for user in db.scalars(stmt):
        if username is not None and user.username == username:
            return "Username is already in use"
        if email is not None and user.email == email:
            return "Email is already in use"
        if normalized_phone is not None and user.phone == normalized_phone:
            return "Phone is already in use"
    return None


def _validate_branch_for_role(*, role_code: RoleCode, branch_id: UUID | None) -> None:
    if role_code != RoleCode.OWNER and branch_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Non-owner users must be assigned to a branch",
        )


def _resolve_create_role_and_branch(
    db: Session,
    actor_user: User,
    payload: UserCreate,
) -> tuple[Role, UUID | None]:
    role = get_role_or_404(db, payload.role_id)
    role_code = RoleCode(role.code)
    branch_id = payload.branch_id

    _ensure_branch_exists(db, branch_id)
    _validate_branch_for_role(role_code=role_code, branch_id=branch_id)

    if is_owner(actor_user):
        return role, branch_id

    if not is_branch_manager(actor_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    require_branch_assignment(actor_user)
    if not can_assign_role(actor_user, role_code):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role assignment is forbidden")

    ensure_same_branch(actor_user, branch_id)
    return role, branch_id


def _resolve_update_role_and_branch(
    db: Session,
    actor_user: User,
    target_user: User,
    payload: UserUpdate,
) -> tuple[RoleCode, UUID | None]:
    data = payload.model_dump(exclude_unset=True)
    role_code = get_role_code(target_user)
    branch_id = target_user.branch_id

    if "role_id" in data and data["role_id"] is not None:
        role = get_role_or_404(db, data["role_id"])
        role_code = RoleCode(role.code)
        if not can_assign_role(actor_user, role_code):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role assignment is forbidden")

    if "branch_id" in data:
        branch_id = data["branch_id"]
        _ensure_branch_exists(db, branch_id)

    _validate_branch_for_role(role_code=role_code, branch_id=branch_id)

    if is_branch_manager(actor_user):
        ensure_same_branch(actor_user, target_user.branch_id)
        ensure_same_branch(actor_user, branch_id)

    return role_code, branch_id


def list_users_for_actor(db: Session, actor_user: User, *, skip: int = 0, limit: int = 100) -> list[User]:
    stmt = user_query().order_by(User.created_at.desc())

    if is_owner(actor_user):
        return list(db.scalars(stmt.offset(skip).limit(limit)))

    if is_branch_manager(actor_user):
        actor_branch_id = require_branch_assignment(actor_user)
        stmt = stmt.join(User.role).where(
            User.branch_id == actor_branch_id,
            Role.code.in_([RoleCode.AD_DIRECTOR.value, RoleCode.MASTER.value, RoleCode.PROMOTER.value]),
        )
        return list(db.scalars(stmt.offset(skip).limit(limit)))

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def get_user_for_actor(db: Session, actor_user: User, user_id: UUID) -> User:
    user = get_user_or_404(db, user_id)

    if is_owner(actor_user):
        return user

    if is_branch_manager(actor_user) and can_manage_user(actor_user, user):
        return user

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def create_user(
    db: Session,
    actor_user: User,
    payload: UserCreate,
    *,
    request: Request | None = None,
) -> User:
    conflict = _ensure_unique_fields(
        db,
        username=payload.username,
        email=payload.email,
        phone=payload.phone,
    )
    if conflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict)

    role, branch_id = _resolve_create_role_and_branch(db, actor_user, payload)
    role_code = RoleCode(role.code)

    user = User(
        username=payload.username,
        email=payload.email,
        phone=normalize_phone(payload.phone) if payload.phone else None,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        middle_name=payload.middle_name,
        status=payload.status,
        is_superuser=role_code == RoleCode.OWNER,
        role_id=role.id,
        branch_id=branch_id,
    )
    db.add(user)
    db.flush()

    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=branch_id,
        entity_type="user",
        entity_id=str(user.id),
        action="user.create",
        payload={"after": serialize_user_for_audit(get_user_or_404(db, user.id))},
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="User created",
        body=(
            f"{actor_user.first_name} {actor_user.last_name} created user "
            f"{user.first_name} {user.last_name} ({role.code})."
        ),
        payload={
            "event": "user.create",
            "user_id": str(user.id),
            "role_code": role.code,
            "branch_id": str(branch_id) if branch_id else None,
        },
        branch_id=branch_id,
        request=request,
    )
    db.commit()
    return get_user_or_404(db, user.id)


def update_user(
    db: Session,
    actor_user: User,
    user: User,
    payload: UserUpdate,
    *,
    request: Request | None = None,
) -> User:
    if not is_owner(actor_user) and not can_manage_user(actor_user, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    data = payload.model_dump(exclude_unset=True)
    conflict = _ensure_unique_fields(
        db,
        username=data.get("username"),
        email=data.get("email"),
        phone=data.get("phone"),
        exclude_user_id=user.id,
    )
    if conflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict)

    role_code, branch_id = _resolve_update_role_and_branch(db, actor_user, user, payload)
    before = serialize_user_for_audit(user)

    for field in ("username", "email", "first_name", "last_name", "middle_name", "status"):
        if field in data:
            setattr(user, field, data[field])

    if is_owner(actor_user) and "is_superuser" in data:
        user.is_superuser = data["is_superuser"]

    if "phone" in data:
        user.phone = normalize_phone(data["phone"]) if data["phone"] else None
    if "password" in data and data["password"]:
        user.password_hash = hash_password(data["password"])
    if "role_id" in data and data["role_id"] is not None:
        user.role_id = data["role_id"]
    if "branch_id" in data:
        user.branch_id = branch_id

    user.is_superuser = role_code == RoleCode.OWNER or user.is_superuser
    if role_code != RoleCode.OWNER:
        user.is_superuser = False

    db.add(user)
    db.flush()
    updated_user = get_user_or_404(db, user.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated_user.branch_id,
        entity_type="user",
        entity_id=str(updated_user.id),
        action="user.update",
        payload={"before": before, "after": serialize_user_for_audit(updated_user)},
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="User updated",
        body=(
            f"User {updated_user.first_name} {updated_user.last_name} was updated by "
            f"{actor_user.first_name} {actor_user.last_name}."
        ),
        payload={"event": "user.update", "user_id": str(updated_user.id)},
        branch_id=updated_user.branch_id,
        request=request,
    )
    db.commit()
    return get_user_or_404(db, user.id)


def update_current_user(
    db: Session,
    actor_user: User,
    payload: CurrentUserUpdate,
    *,
    request: Request | None = None,
) -> User:
    data = payload.model_dump(exclude_unset=True)
    conflict = _ensure_unique_fields(
        db,
        username=data.get("username"),
        email=data.get("email"),
        phone=data.get("phone"),
        exclude_user_id=actor_user.id,
    )
    if conflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict)

    before = serialize_user_for_audit(actor_user)

    for field in ("username", "email", "first_name", "last_name", "middle_name"):
        if field in data:
            setattr(actor_user, field, data[field])

    if "phone" in data:
        actor_user.phone = normalize_phone(data["phone"]) if data["phone"] else None
    if "password" in data and data["password"]:
        actor_user.password_hash = hash_password(data["password"])

    db.add(actor_user)
    db.flush()
    updated_user = get_user_or_404(db, actor_user.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated_user.branch_id,
        entity_type="user",
        entity_id=str(updated_user.id),
        action="user.self_update",
        payload={"before": before, "after": serialize_user_for_audit(updated_user)},
        request=request,
    )
    db.commit()
    return get_user_or_404(db, actor_user.id)


def delete_user(
    db: Session,
    actor_user: User,
    user: User,
    *,
    request: Request | None = None,
    action: str = "user.delete",
) -> None:
    if user.id != actor_user.id and not is_owner(actor_user) and not can_manage_user(actor_user, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    before = serialize_user_for_audit(user)

    try:
        write_audit_log(
            db,
            actor_user=actor_user,
            branch_id=user.branch_id,
            entity_type="user",
            entity_id=str(user.id),
            action=action,
            payload={"before": before},
            request=request,
        )
        notify_owners_about_key_change(
            db,
            actor_user=actor_user,
            title="User removed",
            body=(
                f"User {user.first_name} {user.last_name} was removed by "
                f"{actor_user.first_name} {actor_user.last_name}."
            ),
            payload={"event": action, "user_id": str(user.id)},
            branch_id=user.branch_id,
            request=request,
        )
        db.delete(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User cannot be deleted because related records exist",
        ) from exc


def _archive_identity_fields(user: User) -> None:
    suffix = str(user.id).replace("-", "")[:12]
    user.username = f"archived_{suffix}"
    user.email = f"archived+{suffix}@promouters.local"
    user.phone = None
    user.tg_id = None


def archive_user(
    db: Session,
    actor_user: User,
    user: User,
    *,
    request: Request | None = None,
    action: str = "user.archive",
) -> User:
    if user.id != actor_user.id and not is_owner(actor_user) and not can_manage_user(actor_user, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    before = serialize_user_for_audit(user)
    _archive_identity_fields(user)
    user.status = UserStatus.INACTIVE
    user.is_superuser = False
    db.add(user)
    db.flush()

    archived = get_user_or_404(db, user.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=archived.branch_id,
        entity_type="user",
        entity_id=str(archived.id),
        action=action,
        payload={"before": before, "after": serialize_user_for_audit(archived)},
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="User archived",
        body=(
            f"User {before.get('first_name', '')} {before.get('last_name', '')} was archived by "
            f"{actor_user.first_name} {actor_user.last_name}."
        ),
        payload={"event": action, "user_id": str(archived.id)},
        branch_id=archived.branch_id,
        request=request,
    )
    db.commit()
    return archived
