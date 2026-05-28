from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import Select, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from promouters.models.finance import (
    ExpenseApproval,
    ExpensePlan,
    ExpensePlanItem,
    Payout,
    PayoutRate,
)
from promouters.models.operations import (
    AuditLog,
    BSOAttachment,
    MasterGeoPing,
    MasterRequest,
    MasterRequestComment,
    MasterRequestStatusLog,
)
from promouters.models.routing import (
    GeoPing,
    PhotoReport,
    PromoterSession,
    Route,
    RoutePoint,
)
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


def _purge_branch_dependencies(db: Session, branch_id: str) -> None:
    """Удалить все записи, привязанные к филиалу, в порядке листья → корни.

    Делаем явно через ORM/SQL вместо опоры на ON DELETE CASCADE, потому что
    реальные FK на проде могут быть без каскада (старая схема, ручные миграции).
    Здесь:
      • маршруты со всеми их данными (точки, сессии, GPS, фото, выплаты);
      • payout_rates, expense_plans (с items/approvals);
      • master_requests со вложенными комментариями, лог-статусами, GPS, BSO;
      • users — НЕ удаляются, у них branch_id просто очищается;
      • audit_logs — НЕ удаляются, branch_id очищается.
    """
    # --- Маршруты и их потомки -------------------------------------------------
    route_ids = list(db.scalars(select(Route.id).where(Route.branch_id == branch_id)))
    if route_ids:
        session_ids = list(
            db.scalars(select(PromoterSession.id).where(PromoterSession.route_id.in_(route_ids)))
        )

        # Payouts ссылаются на routes/sessions
        db.query(Payout).filter(Payout.route_id.in_(route_ids)).delete(synchronize_session=False)

        if session_ids:
            db.query(PhotoReport).filter(PhotoReport.session_id.in_(session_ids)).delete(synchronize_session=False)
            db.query(GeoPing).filter(GeoPing.session_id.in_(session_ids)).delete(synchronize_session=False)
            db.query(PromoterSession).filter(PromoterSession.id.in_(session_ids)).delete(synchronize_session=False)

        db.query(RoutePoint).filter(RoutePoint.route_id.in_(route_ids)).delete(synchronize_session=False)
        db.query(Route).filter(Route.id.in_(route_ids)).delete(synchronize_session=False)

    # --- Ставки выплат филиала -------------------------------------------------
    db.query(PayoutRate).filter(PayoutRate.branch_id == branch_id).delete(synchronize_session=False)

    # --- Планы расходов и их потомки ------------------------------------------
    plan_ids = list(db.scalars(select(ExpensePlan.id).where(ExpensePlan.branch_id == branch_id)))
    if plan_ids:
        db.query(ExpenseApproval).filter(ExpenseApproval.expense_plan_id.in_(plan_ids)).delete(synchronize_session=False)
        db.query(ExpensePlanItem).filter(ExpensePlanItem.expense_plan_id.in_(plan_ids)).delete(synchronize_session=False)
        db.query(ExpensePlan).filter(ExpensePlan.id.in_(plan_ids)).delete(synchronize_session=False)

    # --- Заявки мастера и их потомки ------------------------------------------
    request_ids = list(
        db.scalars(select(MasterRequest.id).where(MasterRequest.branch_id == branch_id))
    )
    if request_ids:
        db.query(BSOAttachment).filter(BSOAttachment.master_request_id.in_(request_ids)).delete(synchronize_session=False)
        db.query(MasterGeoPing).filter(MasterGeoPing.master_request_id.in_(request_ids)).delete(synchronize_session=False)
        db.query(MasterRequestStatusLog).filter(
            MasterRequestStatusLog.master_request_id.in_(request_ids)
        ).delete(synchronize_session=False)
        db.query(MasterRequestComment).filter(
            MasterRequestComment.master_request_id.in_(request_ids)
        ).delete(synchronize_session=False)
        db.query(MasterRequest).filter(MasterRequest.id.in_(request_ids)).delete(synchronize_session=False)

    # --- Сбрасываем привязки в живых таблицах ---------------------------------
    db.execute(update(User).where(User.branch_id == branch_id).values(branch_id=None))
    db.execute(update(AuditLog).where(AuditLog.branch_id == branch_id).values(branch_id=None))

    db.flush()


def delete_branch(
    db: Session,
    branch: Branch,
    *,
    actor_user: User,
    request: Request | None = None,
) -> None:
    """Удалить филиал вместе со всеми связанными записями.

    Каскадное удаление выполняется явно в коде (через _purge_branch_dependencies)
    и не зависит от ON DELETE CASCADE в БД — это важно, потому что реальная схема
    на проде может расходиться с моделями.

    Что удаляется:
      • маршруты с точками, GPS-пингами, фото и выплатами;
      • ставки оплаты филиала;
      • планы расходов с items/approvals;
      • заявки мастера со всеми вложениями (комментарии, лог-статусы, GPS, BSO).

    Что сохраняется:
      • пользователи — branch_id обнуляется;
      • записи аудита — branch_id обнуляется.
    """
    before = serialize_branch_for_audit(branch)

    try:
        _purge_branch_dependencies(db, branch.id)

        write_audit_log(
            db,
            actor_user=actor_user,
            branch_id=None,
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
            branch_id=None,
            request=request,
        )

        db.delete(branch)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Branch cannot be deleted: {exc.orig}",
        ) from exc
