from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from promouters.api.deps import get_current_user
from promouters.db.session import get_db
from promouters.models.enums import PayoutStatus
from promouters.models.users import User
from promouters.schemas.finance import (
    PayoutListFilters,
    PayoutRateCreate,
    PayoutRateRead,
    PayoutRateUpdate,
    PayoutRead,
    PayoutSummaryRead,
)
from promouters.services.finance import (
    create_payout_rate,
    get_payout_rate_or_404,
    list_payout_rates_for_actor,
    list_payouts_for_actor,
    summarize_payouts_by_promoter,
    to_payout_rate_read,
    to_payout_read,
    update_payout_rate,
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


@router.get("/payouts", response_model=list[PayoutRead])
def get_payouts(
    promoter_id: UUID | None = Query(default=None),
    route_id: UUID | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    status_filter: PayoutStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PayoutRead]:
    payouts = list_payouts_for_actor(
        db,
        current_user,
        filters=PayoutListFilters(
            promoter_id=promoter_id,
            route_id=route_id,
            branch_id=branch_id,
            status=status_filter,
        ),
    )
    return [to_payout_read(payout) for payout in payouts]


@router.get("/payouts/summary/by-promoter", response_model=list[PayoutSummaryRead])
def get_payout_summary_by_promoter(
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PayoutSummaryRead]:
    payouts = list_payouts_for_actor(
        db,
        current_user,
        filters=PayoutListFilters(branch_id=branch_id),
    )
    return summarize_payouts_by_promoter(payouts)
