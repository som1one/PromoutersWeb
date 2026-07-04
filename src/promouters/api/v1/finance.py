from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from promouters.api.deps import get_current_user
from promouters.db.session import get_db
from promouters.models.enums import PayoutStatus
from promouters.models.users import User
from promouters.schemas.finance import (
    PayoutCreate,
    PayoutListFilters,
    PayoutListResponse,
    PayoutRateCreate,
    PayoutRateRead,
    PayoutRateUpdate,
    PayoutRead,
    PayoutSummaryRead,
    PromoterPaymentDetailsCreate,
    PromoterPaymentDetailsRead,
)
from promouters.services.finance import (
    approve_and_pay_payout,
    approve_payout,
    create_manual_payout,
    create_payout_rate,
    get_payment_details_for_user,
    get_payout_or_404,
    get_payout_rate_or_404,
    list_payout_rates_for_actor,
    list_payouts_for_actor,
    list_payouts_raw_for_actor,
    mark_payout_paid,
    save_payment_proof_file,
    summarize_payouts_by_promoter,
    to_payout_rate_read,
    to_payout_read,
    to_payment_details_read,
    update_payout_rate,
    upsert_payment_details,
)

router = APIRouter(tags=["finance"])


@router.get("/payout-rates", response_model=list[PayoutRateRead])
def get_payout_rates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PayoutRateRead]:
    return [to_payout_rate_read(rate) for rate in list_payout_rates_for_actor(db, current_user)]


@router.post("/payout-rates", response_model=PayoutRateRead, status_code=status.HTTP_201_CREATED)
def create_payout_rate_endpoint(
    payload: PayoutRateCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PayoutRateRead:
    return to_payout_rate_read(create_payout_rate(db, current_user, payload, request=request))


@router.patch("/payout-rates/{payout_rate_id}", response_model=PayoutRateRead)
def update_payout_rate_endpoint(
    payout_rate_id: UUID,
    payload: PayoutRateUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PayoutRateRead:
    payout_rate = get_payout_rate_or_404(db, payout_rate_id)
    return to_payout_rate_read(update_payout_rate(db, current_user, payout_rate, payload, request=request))


@router.post("/payouts", response_model=PayoutRead, status_code=status.HTTP_201_CREATED)
def create_payout_endpoint(
    payload: PayoutCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PayoutRead:
    """Manually create a payout (settlement) for a promoter."""
    payout = create_manual_payout(db, current_user, payload, request=request)
    return to_payout_read(payout)


@router.get("/payouts", response_model=PayoutListResponse)
def get_payouts(
    promoter_id: UUID | None = Query(default=None),
    route_id: UUID | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    status_filter: PayoutStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, min_length=2),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PayoutListResponse:
    return list_payouts_for_actor(
        db,
        current_user,
        filters=PayoutListFilters(
            promoter_id=promoter_id,
            route_id=route_id,
            branch_id=branch_id,
            status=status_filter,
            search=search,
            page=page,
            page_size=page_size,
        ),
    )


@router.get("/payouts/summary/by-promoter", response_model=list[PayoutSummaryRead])
def get_payout_summary_by_promoter(
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PayoutSummaryRead]:
    payouts = list_payouts_raw_for_actor(
        db,
        current_user,
        filters=PayoutListFilters(branch_id=branch_id),
    )
    return summarize_payouts_by_promoter(payouts)


@router.post("/payouts/{payout_id}/approve-and-pay", response_model=PayoutRead)
async def approve_and_pay_payout_endpoint(
    payout_id: UUID,
    request: Request,
    file: UploadFile = File(..., description="Скриншот перевода (обязательно)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PayoutRead:
    """Approve and pay in one step. Requires payment proof screenshot."""
    payout = get_payout_or_404(db, payout_id)
    # Save proof file
    content = await file.read()
    proof_path = save_payment_proof_file(content, file.filename or "proof.png", payout_id)
    updated = approve_and_pay_payout(db, current_user, payout, payment_proof_path=proof_path, request=request)
    return to_payout_read(updated)


@router.post("/payouts/{payout_id}/approve", response_model=PayoutRead)
def approve_payout_endpoint(
    payout_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PayoutRead:
    payout = get_payout_or_404(db, payout_id)
    updated = approve_payout(db, current_user, payout, request=request)
    return to_payout_read(updated)


@router.post("/payouts/{payout_id}/pay", response_model=PayoutRead)
async def mark_payout_paid_endpoint(
    payout_id: UUID,
    request: Request,
    file: UploadFile = File(..., description="Скриншот перевода (обязательно)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PayoutRead:
    """Mark payout as paid. Requires payment proof screenshot."""
    payout = get_payout_or_404(db, payout_id)
    content = await file.read()
    proof_path = save_payment_proof_file(content, file.filename or "proof.png", payout_id)
    updated = mark_payout_paid(db, current_user, payout, payment_proof_path=proof_path, request=request)
    return to_payout_read(updated)


# --- Promoter Payment Details ---


@router.get("/payment-details/me", response_model=PromoterPaymentDetailsRead | None)
def get_my_payment_details(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PromoterPaymentDetailsRead | None:
    """Get current user's payment details."""
    pd = get_payment_details_for_user(db, current_user.id)
    if pd is None:
        return None
    return to_payment_details_read(pd)


@router.post("/payment-details/me", response_model=PromoterPaymentDetailsRead, status_code=status.HTTP_201_CREATED)
def set_my_payment_details(
    payload: PromoterPaymentDetailsCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PromoterPaymentDetailsRead:
    """Create or update current user's payment details."""
    pd = upsert_payment_details(db, current_user.id, payload)
    return to_payment_details_read(pd)


@router.get("/payment-details/{user_id}", response_model=PromoterPaymentDetailsRead | None)
def get_user_payment_details(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PromoterPaymentDetailsRead | None:
    """Get payment details for a specific promoter (managers only)."""
    from promouters.services.access import require_route_manager
    require_route_manager(current_user)
    pd = get_payment_details_for_user(db, user_id)
    if pd is None:
        return None
    return to_payment_details_read(pd)
