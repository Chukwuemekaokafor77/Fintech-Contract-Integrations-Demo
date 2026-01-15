import datetime as dt
import uuid

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.time import utcnow


class Base(DeclarativeBase):
    pass


class DepositAccount(Base):
    __tablename__ = "deposit_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    opened_on: Mapped[dt.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="OPEN")

    annual_interest_rate: Mapped[str] = mapped_column(String, nullable=False)
    day_count_basis: Mapped[int] = mapped_column(Integer, nullable=False, default=365)

    current_balance: Mapped[str] = mapped_column(String, nullable=False, default="0")
    accrued_interest: Mapped[str] = mapped_column(String, nullable=False, default="0")
    last_accrual_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class LoanAccount(Base):
    __tablename__ = "loan_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    opened_on: Mapped[dt.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="OPEN")

    principal: Mapped[str] = mapped_column(String, nullable=False)
    annual_interest_rate: Mapped[str] = mapped_column(String, nullable=False)
    day_count_basis: Mapped[int] = mapped_column(Integer, nullable=False, default=365)

    outstanding_principal: Mapped[str] = mapped_column(String, nullable=False)
    accrued_interest: Mapped[str] = mapped_column(String, nullable=False, default="0")

    last_accrual_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    effective_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    account_type: Mapped[str] = mapped_column(String, nullable=False)
    account_id: Mapped[str] = mapped_column(String, nullable=False)

    txn_id: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)

    debit_account: Mapped[str] = mapped_column(String, nullable=False)
    credit_account: Mapped[str] = mapped_column(String, nullable=False)

    amount: Mapped[str] = mapped_column(String, nullable=False)


class DomainEvent(Base):
    __tablename__ = "domain_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    aggregate_type: Mapped[str] = mapped_column(String, nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String, nullable=False)

    event_type: Mapped[str] = mapped_column(String, nullable=False)
    event_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    event_id: Mapped[str] = mapped_column(String, ForeignKey("domain_events.id"), nullable=False)
    destination: Mapped[str] = mapped_column(String, nullable=False)

    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    next_attempt_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)

    event: Mapped[DomainEvent] = relationship("DomainEvent")


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    target_url: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class QueueMessage(Base):
    __tablename__ = "queue_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    topic: Mapped[str] = mapped_column(String, nullable=False, default="domain_events")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
