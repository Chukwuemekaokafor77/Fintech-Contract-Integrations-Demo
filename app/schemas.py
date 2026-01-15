import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, Field


class DepositAccountOpenRequest(BaseModel):
    opened_on: dt.date
    annual_interest_rate: Decimal = Field(..., ge=Decimal("0"))
    day_count_basis: int = Field(365, ge=360)
    idempotency_key: str | None = None


class DepositAccountResponse(BaseModel):
    id: str
    opened_on: dt.date
    status: str
    annual_interest_rate: Decimal
    day_count_basis: int
    current_balance: Decimal
    accrued_interest: Decimal


class MoneyRequest(BaseModel):
    amount: Decimal = Field(..., gt=Decimal("0"))
    effective_date: dt.date
    idempotency_key: str | None = None


class AccrueInterestRequest(BaseModel):
    as_of_date: dt.date


class ApplyMonthEndRequest(BaseModel):
    effective_date: dt.date


class WebhookSubscriptionCreateRequest(BaseModel):
    target_url: str


class WebhookSubscriptionResponse(BaseModel):
    id: str
    target_url: str
    enabled: bool


class DispatchOutboxRequest(BaseModel):
    max_messages: int = Field(50, ge=1, le=500)


class OutboxReplayRequest(BaseModel):
    aggregate_type: str | None = None
    aggregate_id: str | None = None
    destination: str | None = None


class LoanAccountOpenRequest(BaseModel):
    opened_on: dt.date
    principal: Decimal = Field(..., gt=Decimal("0"))
    annual_interest_rate: Decimal = Field(..., ge=Decimal("0"))
    day_count_basis: int = Field(365, ge=360)
    idempotency_key: str | None = None


class LoanAccountResponse(BaseModel):
    id: str
    opened_on: dt.date
    status: str
    principal: Decimal
    annual_interest_rate: Decimal
    day_count_basis: int
    outstanding_principal: Decimal
    accrued_interest: Decimal
