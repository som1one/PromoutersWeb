from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from promouters.models.enums import PayoutRateType, PayoutStatus, RoleCode, RouteStatus
from promouters.models.finance import Payout, PayoutRate
from promouters.models.routing import PromoterSession, Route
from promouters.models.users import Branch, Role, User
from promouters.schemas.finance import (
    PayoutListFilters,
    PayoutRateCreate,
    PayoutRateRead,
    PayoutRateUpdate,
    PayoutRead,
    PayoutSummaryRead,
)
from promouters.services.access import (
    ensure_same_branch,
    get_role_code,
    is_owner,
    require_branch_assignment,
    require_route_manager,
)
from promouters.services.audit import write_audit_log
from promouters.services.notifications import notify_owners_about_key_change

MONEY_QUANT = Decimal("0.01")


def _full_name(user: User | None) -> str:
    if user is None:
        return ""
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    return full_name or user.username


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def payout_rate_query() -> Select[tuple[PayoutRate]]:
    return (
        select(PayoutRate)
        .options(
            joinedload(PayoutRate.branch),
            joinedload(PayoutRate.role),
            joinedload(PayoutRate.created_by),
        )
    )


def payout_query() -> Select[tuple[Payout]]:
    return (
        select(Payout)
        .options(
            joinedload(Payout.route).joinedload(Route.branch),
            joinedload(Payout.route).joinedload(Route.payout_rate),
            joinedload(Payout.route).joinedload(Route.promoter),
            joinedload(Payout.promoter).joinedload(User.branch),
            joinedload(Payout.payout_rate),
            joinedload(Payout.session),
        )
    )


def get_payout_rate_or_404(db: Session, payout_rate_id: UUID) -> PayoutRate:
    payout_rate = db.scalar(payout_rate_query().where(PayoutRate.id == payout_rate_id))
    if payout_rate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout rate not found")
    return payout_rate


def get_payout_or_404(db: Session, payout_id: UUID) -> Payout:
    payout = db.scalar(payout_query().where(Payout.id == payout_id))
    if payout is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout not found")
    return payout


def _ensure_branch_exists(db: Session, branch_id: UUID | None) -> None:
    if branch_id is None:
        return
    if db.get(Branch, branch_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")


def _ensure_role_exists(db: Session, role_id: UUID | None) -> None:
    if role_id is None:
        return
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")


def _ensure_actor_can_manage_rate_scope(actor_user: User, branch_id: UUID | None) -> None:
    require_route_manager(actor_user)
    if not is_owner(actor_user):
        ensure_same_branch(actor_user, branch_id)


def to_payout_rate_read(payout_rate: PayoutRate) -> PayoutRateRead:
    return PayoutRateRead(
        id=payout_rate.id,
        name=payout_rate.name,
        rate_type=payout_rate.rate_type.value,
        amount=payout_rate.amount,
        currency=payout_rate.currency,
        per_unit_name=payout_rate.per_unit_name,
        active_from=payout_rate.active_from,
        active_to=payout_rate.active_to,
        is_active=payout_rate.is_active,
        branch_id=payout_rate.branch_id,
        branch_name=payout_rate.branch.name if payout_rate.branch else None,
        role_id=payout_rate.role_id,
        role_name=payout_rate.role.name if payout_rate.role else None,
        created_by_id=payout_rate.created_by_id,
        created_by_name=_full_name(payout_rate.created_by),
        created_at=payout_rate.created_at,
        updated_at=payout_rate.updated_at,
    )


def to_payout_read(payout: Payout) -> PayoutRead:
    route = payout.route
    payout_rate = payout.payout_rate or (route.payout_rate if route else None)
    return PayoutRead(
        id=payout.id,
        route_id=payout.route_id,
        route_title=route.title if route else "",
        work_date=route.work_date if route else datetime.now(UTC).date(),
        session_id=payout.session_id,
        promoter_id=payout.promoter_id,
        promoter_name=_full_name(payout.promoter),
        payout_rate_id=payout.payout_rate_id,
        payout_rate_name=payout_rate.name if payout_rate else None,
        payout_rate_type=payout_rate.rate_type.value if payout_rate else None,
        amount=payout.amount,
        currency=payout.currency,
        units=payout.units,
        notes=payout.notes,
        status=payout.status.value,
        calculated_at=payout.calculated_at,
        approved_at=payout.approved_at,
        paid_at=payout.paid_at,
        calculation_details=payout.calculation_details,
        created_at=payout.created_at,
        updated_at=payout.updated_at,
    )


def list_payout_rates_for_actor(db: Session, actor_user: User) -> list[PayoutRate]:
    stmt = payout_rate_query().order_by(PayoutRate.created_at.desc())
    if not is_owner(actor_user):
        stmt = stmt.where(
            (PayoutRate.branch_id == require_branch_assignment(actor_user)) | (PayoutRate.branch_id.is_(None))
        )
    return list(db.scalars(stmt))


def create_payout_rate(
    db: Session,
    actor_user: User,
    payload: PayoutRateCreate,
    *,
    request: Request | None = None,
) -> PayoutRate:
    _ensure_actor_can_manage_rate_scope(actor_user, payload.branch_id)
    _ensure_branch_exists(db, payload.branch_id)
    _ensure_role_exists(db, payload.role_id)

    payout_rate = PayoutRate(
        name=payload.name.strip(),
        rate_type=payload.rate_type,
        amount=_quantize(payload.amount),
        currency=payload.currency,
        per_unit_name=payload.per_unit_name.strip() if payload.per_unit_name else None,
        active_from=payload.active_from,
        active_to=payload.active_to,
        is_active=payload.is_active,
        branch_id=payload.branch_id,
        role_id=payload.role_id,
        created_by_id=actor_user.id,
    )
    db.add(payout_rate)
    db.flush()

    created = get_payout_rate_or_404(db, payout_rate.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=created.branch_id,
        entity_type="payout_rate",
        entity_id=str(created.id),
        action="payout_rate.create",
        payload={"after": to_payout_rate_read(created).model_dump(mode="json")},
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="New payout rate created",
        body=f"{_full_name(actor_user)} created payout rate '{created.name}'.",
        payload={
            "event": "payout_rate.create",
            "payout_rate_id": str(created.id),
            "branch_id": str(created.branch_id) if created.branch_id else None,
        },
        branch_id=created.branch_id,
        request=request,
    )
    db.commit()
    return get_payout_rate_or_404(db, payout_rate.id)


def update_payout_rate(
    db: Session,
    actor_user: User,
    payout_rate: PayoutRate,
    payload: PayoutRateUpdate,
    *,
    request: Request | None = None,
) -> PayoutRate:
    _ensure_actor_can_manage_rate_scope(actor_user, payout_rate.branch_id)
    before = to_payout_rate_read(payout_rate).model_dump(mode="json")
    data = payload.model_dump(exclude_unset=True)

    if "branch_id" in data:
        _ensure_actor_can_manage_rate_scope(actor_user, data["branch_id"])
        _ensure_branch_exists(db, data["branch_id"])
    if "role_id" in data:
        _ensure_role_exists(db, data["role_id"])
    if "amount" in data and data["amount"] is not None:
        data["amount"] = _quantize(data["amount"])
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    if "per_unit_name" in data and data["per_unit_name"] is not None:
        data["per_unit_name"] = data["per_unit_name"].strip()

    for field, value in data.items():
        setattr(payout_rate, field, value)

    db.add(payout_rate)
    db.flush()

    updated = get_payout_rate_or_404(db, payout_rate.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated.branch_id,
        entity_type="payout_rate",
        entity_id=str(updated.id),
        action="payout_rate.update",
        payload={"before": before, "after": to_payout_rate_read(updated).model_dump(mode="json")},
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="Payout rate updated",
        body=f"{_full_name(actor_user)} updated payout rate '{updated.name}'.",
        payload={
            "event": "payout_rate.update",
            "payout_rate_id": str(updated.id),
            "branch_id": str(updated.branch_id) if updated.branch_id else None,
        },
        branch_id=updated.branch_id,
        request=request,
    )
    db.commit()
    return get_payout_rate_or_404(db, payout_rate.id)


def list_payouts_for_actor(
    db: Session,
    actor_user: User,
    *,
    filters: PayoutListFilters,
) -> list[Payout]:
    stmt = payout_query().order_by(Payout.calculated_at.desc().nullslast(), Payout.created_at.desc())
    role_code = get_role_code(actor_user)

    if role_code == RoleCode.OWNER:
        pass
    elif role_code in {RoleCode.BRANCH_MANAGER, RoleCode.AD_DIRECTOR}:
        stmt = stmt.where(Payout.route.has(Route.branch_id == require_branch_assignment(actor_user)))
    elif role_code == RoleCode.PROMOTER:
        stmt = stmt.where(Payout.promoter_id == actor_user.id)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if filters.promoter_id is not None:
        stmt = stmt.where(Payout.promoter_id == filters.promoter_id)
    if filters.route_id is not None:
        stmt = stmt.where(Payout.route_id == filters.route_id)
    if filters.branch_id is not None:
        stmt = stmt.where(Payout.route.has(Route.branch_id == filters.branch_id))
    if filters.status is not None:
        stmt = stmt.where(Payout.status == filters.status)

    return list(db.scalars(stmt))


def summarize_payouts_by_promoter(payouts: list[Payout]) -> list[PayoutSummaryRead]:
    grouped: dict[UUID, list[Payout]] = defaultdict(list)
    for payout in payouts:
        grouped[payout.promoter_id].append(payout)

    result: list[PayoutSummaryRead] = []
    for promoter_id, promoter_payouts in grouped.items():
        total_amount = sum((payout.amount for payout in promoter_payouts), start=Decimal("0.00"))
        result.append(
            PayoutSummaryRead(
                promoter_id=promoter_id,
                promoter_name=_full_name(promoter_payouts[0].promoter),
                payout_count=len(promoter_payouts),
                total_amount=_quantize(total_amount),
                currency=promoter_payouts[0].currency,
                payouts=[to_payout_read(payout) for payout in promoter_payouts],
            )
        )
    result.sort(key=lambda item: item.promoter_name.lower())
    return result


def _build_hourly_payout(rate: PayoutRate, session: PromoterSession) -> tuple[Decimal, Decimal, dict, str]:
    total_minutes = session.total_minutes or 0
    units = _quantize(Decimal(total_minutes) / Decimal(60))
    amount = _quantize(rate.amount * units)
    details = {
        "rate_type": rate.rate_type.value,
        "rate_amount": str(rate.amount),
        "units": str(units),
        "unit_label": "hours",
        "total_minutes": total_minutes,
        "formula": f"{rate.amount} * {units}",
    }
    notes = f"Hourly payout: {rate.amount} x {units}h"
    return units, amount, details, notes


def _build_leaflet_payout(rate: PayoutRate, session: PromoterSession) -> tuple[Decimal, Decimal, dict, str]:
    leaflet_count = session.leaflet_count or 0
    units = _quantize(Decimal(leaflet_count))
    amount = _quantize(rate.amount * units)
    details = {
        "rate_type": rate.rate_type.value,
        "rate_amount": str(rate.amount),
        "units": str(units),
        "unit_label": "leaflets",
        "leaflet_count": leaflet_count,
        "formula": f"{rate.amount} * {units}",
    }
    notes = f"Per leaflet payout: {rate.amount} x {leaflet_count}"
    return units, amount, details, notes


def calculate_payout_for_route(
    db: Session,
    *,
    route: Route,
    session: PromoterSession,
    actor_user: User | None,
    request: Request | None = None,
) -> Payout | None:
    if route.status != RouteStatus.COMPLETED or route.promoter_id is None or route.payout_rate_id is None:
        return None

    payout_rate = db.scalar(payout_rate_query().where(PayoutRate.id == route.payout_rate_id))
    if payout_rate is None:
        return None

    if payout_rate.rate_type == PayoutRateType.HOURLY:
        units, amount, details, notes = _build_hourly_payout(payout_rate, session)
    elif payout_rate.rate_type == PayoutRateType.PER_LEAFLET:
        units, amount, details, notes = _build_leaflet_payout(payout_rate, session)
    else:
        return None

    payout = db.scalar(select(Payout).where(Payout.session_id == session.id))
    if payout is None:
        payout = Payout(
            route_id=route.id,
            session_id=session.id,
            promoter_id=route.promoter_id,
            payout_rate_id=payout_rate.id,
            amount=amount,
            currency=payout_rate.currency,
            units=units,
            notes=notes,
            calculation_details=details,
            status=PayoutStatus.CALCULATED,
            calculated_at=datetime.now(UTC),
        )
        db.add(payout)
        db.flush()
    else:
        payout.amount = amount
        payout.currency = payout_rate.currency
        payout.units = units
        payout.notes = notes
        payout.payout_rate_id = payout_rate.id
        payout.calculation_details = details
        payout.status = PayoutStatus.CALCULATED
        payout.calculated_at = datetime.now(UTC)
        db.add(payout)
        db.flush()

    calculated = get_payout_or_404(db, payout.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=route.branch_id,
        entity_type="payout",
        entity_id=str(calculated.id),
        action="payout.calculate",
        payload={"after": to_payout_read(calculated).model_dump(mode="json")},
        request=request,
    )
    return calculated



def _ensure_can_change_payout(actor_user: User, payout: Payout) -> None:
    """Только owner и branch_manager своего филиала могут менять статусы выплат."""
    if is_owner(actor_user):
        return
    role_code = get_role_code(actor_user)
    if role_code not in {RoleCode.BRANCH_MANAGER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    branch_id = payout.route.branch_id if payout.route else None
    if branch_id is None or branch_id != require_branch_assignment(actor_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-branch payout change is forbidden")


def approve_payout(
    db: Session,
    actor_user: User,
    payout: Payout,
    *,
    request: Request | None = None,
) -> Payout:
    """CALCULATED -> APPROVED."""
    _ensure_can_change_payout(actor_user, payout)
    if payout.status != PayoutStatus.CALCULATED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Approve allowed only for CALCULATED, got {payout.status.value}",
        )
    before = to_payout_read(payout).model_dump(mode="json")
    payout.status = PayoutStatus.APPROVED
    payout.approved_at = datetime.now(UTC)
    payout.approved_by_id = actor_user.id
    db.add(payout)
    db.flush()

    updated = get_payout_or_404(db, payout.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=payout.route.branch_id if payout.route else None,
        entity_type="payout",
        entity_id=str(payout.id),
        action="payout.approve",
        payload={"before": before, "after": to_payout_read(updated).model_dump(mode="json")},
        request=request,
    )
    db.commit()
    return get_payout_or_404(db, payout.id)


def mark_payout_paid(
    db: Session,
    actor_user: User,
    payout: Payout,
    *,
    request: Request | None = None,
) -> Payout:
    """APPROVED -> PAID."""
    _ensure_can_change_payout(actor_user, payout)
    if payout.status != PayoutStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mark paid allowed only for APPROVED, got {payout.status.value}",
        )
    before = to_payout_read(payout).model_dump(mode="json")
    payout.status = PayoutStatus.PAID
    payout.paid_at = datetime.now(UTC)
    db.add(payout)
    db.flush()

    updated = get_payout_or_404(db, payout.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=payout.route.branch_id if payout.route else None,
        entity_type="payout",
        entity_id=str(payout.id),
        action="payout.mark_paid",
        payload={"before": before, "after": to_payout_read(updated).model_dump(mode="json")},
        request=request,
    )
    db.commit()
    return get_payout_or_404(db, payout.id)


def cancel_payout(
    db: Session,
    actor_user: User,
    payout: Payout,
    *,
    request: Request | None = None,
) -> Payout:
    _ensure_can_change_payout(actor_user, payout)
    if payout.status == PayoutStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot cancel a paid payout",
        )
    before = to_payout_read(payout).model_dump(mode="json")
    payout.status = PayoutStatus.CANCELLED
    db.add(payout)
    db.flush()
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=payout.route.branch_id if payout.route else None,
        entity_type="payout",
        entity_id=str(payout.id),
        action="payout.cancel",
        payload={"before": before, "after": to_payout_read(payout).model_dump(mode="json")},
        request=request,
    )
    db.commit()
    return get_payout_or_404(db, payout.id)
