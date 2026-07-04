from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from promouters.models.enums import PayoutRateType, PayoutStatus


SUPPORTED_PAYOUT_RATE_TYPES = {PayoutRateType.HOURLY, PayoutRateType.PER_LEAFLET}


class PayoutRateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    rate_type: PayoutRateType
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=12)
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    per_unit_name: str | None = Field(default=None, max_length=50)
    active_from: date | None = None
    active_to: date | None = None
    is_active: bool = True
    branch_id: UUID | None = None
    role_id: UUID | None = None

    @field_validator("rate_type")
    @classmethod
    def validate_supported_types(cls, value: PayoutRateType) -> PayoutRateType:
        if value not in SUPPORTED_PAYOUT_RATE_TYPES:
            raise ValueError("Only hourly and per_leaflet payout rates are supported in MVP")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class PayoutRateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    rate_type: PayoutRateType | None = None
    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2, max_digits=12)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    per_unit_name: str | None = Field(default=None, max_length=50)
    active_from: date | None = None
    active_to: date | None = None
    is_active: bool | None = None
    branch_id: UUID | None = None
    role_id: UUID | None = None

    @field_validator("rate_type")
    @classmethod
    def validate_supported_types(cls, value: PayoutRateType | None) -> PayoutRateType | None:
        if value is not None and value not in SUPPORTED_PAYOUT_RATE_TYPES:
            raise ValueError("Only hourly and per_leaflet payout rates are supported in MVP")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class PayoutRateRead(BaseModel):
    id: UUID
    name: str
    rate_type: str
    amount: Decimal
    currency: str
    per_unit_name: str | None
    active_from: date | None
    active_to: date | None
    is_active: bool
    branch_id: UUID | None
    branch_name: str | None
    role_id: UUID | None
    role_name: str | None
    created_by_id: UUID
    created_by_name: str
    created_at: datetime
    updated_at: datetime


class PayoutRead(BaseModel):
    id: UUID
    route_id: UUID | None
    route_title: str
    work_date: date | None
    session_id: UUID | None
    promoter_id: UUID
    promoter_name: str
    payout_rate_id: UUID | None
    payout_rate_name: str | None
    payout_rate_type: str | None
    amount: Decimal
    currency: str
    units: Decimal | None
    notes: str | None
    status: str
    payment_proof_path: str | None = None
    payment_proof_url: str | None = None
    promoter_phone: str | None = None
    promoter_bank: str | None = None
    promoter_card_holder: str | None = None
    calculated_at: datetime | None
    approved_at: datetime | None
    paid_at: datetime | None
    calculation_details: dict | None
    created_at: datetime
    updated_at: datetime


class PayoutCreate(BaseModel):
    """Schema for manual payout creation from the settlements page."""
    promoter_id: UUID
    rate_type: PayoutRateType
    amount_per_unit: Decimal = Field(gt=0)
    units: Decimal = Field(gt=0)
    notes: str | None = Field(default=None, max_length=500)
    session_date: date | None = None

    @field_validator("rate_type")
    @classmethod
    def validate_rate_type(cls, value: PayoutRateType) -> PayoutRateType:
        if value not in {PayoutRateType.HOURLY, PayoutRateType.PER_LEAFLET}:
            raise ValueError("Only hourly and per_leaflet are supported for manual payouts")
        return value


class PayoutListFilters(BaseModel):
    promoter_id: UUID | None = None
    route_id: UUID | None = None
    branch_id: UUID | None = None
    status: PayoutStatus | None = None
    search: str | None = Field(default=None, min_length=2)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)


class PayoutListResponse(BaseModel):
    items: list[PayoutRead]
    total: int
    page: int
    page_size: int


class PayoutSummaryRead(BaseModel):
    promoter_id: UUID
    promoter_name: str
    payout_count: int
    total_amount: Decimal
    currency: str
    payouts: list[PayoutRead]


class PromoterPaymentDetailsRead(BaseModel):
    """Реквизиты промоутера для отображения в интерфейсе."""
    id: UUID
    user_id: UUID
    phone_number: str
    bank_name: str
    card_holder_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PromoterPaymentDetailsCreate(BaseModel):
    """Создание/обновление реквизитов промоутером через бот."""
    phone_number: str = Field(min_length=10, max_length=32)
    bank_name: str = Field(min_length=2, max_length=128)
    card_holder_name: str = Field(min_length=2, max_length=200)

