from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from promouters.models.users import Branch, User
from promouters.schemas.branches import BranchCreate, BranchRead, BranchUpdate
from promouters.services.audit import write_audit_log
from promouters.services.notifications import notify_owners_about_key_change


def branch_query() -> Select[tuple[Branch]]:
    return select(Branch)


def to_branch_read(branch: Branch) -> BranchRead:
    return BranchRead(
        id=branch.id,
        name=branch.name,
        code=branch.code,
        city=branch.city,
        address=branch.address,
        is_active=branch.is_active,
        created_at=branch.created_at,
        updated_at=branch.updated_at,
    )


def serialize_branch_for_audit(branch: Branch) -> dict:
    return to_branch_read(branch).model_dump(mode="json")


def get_branch_or_404(db: Session, branch_id: UUID) -> Branch:
    branch = db.scalar(branch_query().where(Branch.id == branch_id))
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return branch


def ensure_unique_branch_code(db: Session, code: str | None, *, exclude_branch_id: UUID | None = None) -> None:
    if code is None:
        return

    stmt = branch_query().where(Branch.code == code)
    if exclude_branch_id is not None:
        stmt = stmt.where(Branch.id != exclude_branch_id)

    if db.scalar(stmt) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Branch code is already in use")


def list_branches(db: Session, *, branch_id: UUID | None = None) -> list[Branch]:
    stmt = branch_query().order_by(Branch.created_at.desc())
    if branch_id is not None:
        stmt = stmt.where(Branch.id == branch_id)
    return list(db.scalars(stmt))


def create_branch(
    db: Session,
    payload: BranchCreate,
    *,
    actor_user: User,
    request: Request | None = None,
) -> Branch:
    ensure_unique_branch_code(db, payload.code)

    branch = Branch(
        name=payload.name,
        code=payload.code,
        city=payload.city,
        address=payload.address,
        is_active=payload.is_active,
    )
    db.add(branch)
    db.flush()
    created_branch = get_branch_or_404(db, branch.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=created_branch.id,
        entity_type="branch",
        entity_id=str(created_branch.id),
        action="branch.create",
        payload={"after": serialize_branch_for_audit(created_branch)},
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="Branch created",
        body=f"Branch '{created_branch.name}' was created.",
        payload={"event": "branch.create", "branch_id": str(created_branch.id)},
        branch_id=created_branch.id,
        request=request,
    )
    db.commit()
    return get_branch_or_404(db, branch.id)


def update_branch(
    db: Session,
    branch: Branch,
    payload: BranchUpdate,
    *,
    actor_user: User,
    request: Request | None = None,
) -> Branch:
    data = payload.model_dump(exclude_unset=True)
    if "code" in data:
        ensure_unique_branch_code(db, data["code"], exclude_branch_id=branch.id)

    before = serialize_branch_for_audit(branch)

    for field in ("name", "code", "city", "address", "is_active"):
        if field in data:
            setattr(branch, field, data[field])

    db.add(branch)
    db.flush()
    updated_branch = get_branch_or_404(db, branch.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated_branch.id,
        entity_type="branch",
        entity_id=str(updated_branch.id),
        action="branch.update",
        payload={"before": before, "after": serialize_branch_for_audit(updated_branch)},
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="Branch updated",
        body=f"Branch '{updated_branch.name}' was updated.",
        payload={"event": "branch.update", "branch_id": str(updated_branch.id)},
        branch_id=updated_branch.id,
        request=request,
    )
    db.commit()
    return get_branch_or_404(db, branch.id)


def delete_branch(
    db: Session,
    branch: Branch,
    *,
    actor_user: User,
    request: Request | None = None,
) -> None:
    """Удалить филиал вместе со всеми связанными записями.

    Postgres каскадно сносит маршруты (с точками, сессиями, GPS, фото),
    выплаты, ставки выплат, планы расходов, заявки мастера и их вложения.
    Пользователи филиала НЕ удаляются — у них branch_id просто становится NULL.
    Записи аудита сохраняются (branch_id затирается на NULL).
    """
    try:
        before = serialize_branch_for_audit(branch)
        write_audit_log(
            db,
            actor_user=actor_user,
            branch_id=branch.id,
            entity_type="branch",
            entity_id=str(branch.id),
            action="branch.delete",
            payload={"before": before},
            request=request,
        )
        notify_owners_about_key_change(
            db,
            actor_user=actor_user,
            title="Branch removed",
            body=f"Branch '{branch.name}' was removed.",
            payload={"event": "branch.delete", "branch_id": str(branch.id)},
            branch_id=branch.id,
            request=request,
        )
        db.delete(branch)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Branch cannot be deleted because of database constraints",
        ) from exc
