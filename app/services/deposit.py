import datetime as dt
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import DepositAccount, LedgerEntry
from app.money import q, q_rate
from app.services.events import append_event, find_event_by_idempotency_key
from app.time import utcnow


AGGREGATE_TYPE = "deposit_account"


def _dec(s: str) -> Decimal:
    return Decimal(s)


def open_account(
    db: Session,
    *,
    opened_on: dt.date,
    annual_interest_rate: Decimal,
    day_count_basis: int,
    idempotency_key: str | None,
) -> DepositAccount:
    if idempotency_key:
        existing = find_event_by_idempotency_key(
            db,
            aggregate_type=AGGREGATE_TYPE,
            idempotency_key=idempotency_key,
        )
        if existing and existing.event_type == "DEPOSIT_ACCOUNT_OPENED":
            acct = db.get(DepositAccount, existing.aggregate_id)
            if acct:
                return acct

    acct = DepositAccount(
        opened_on=opened_on,
        annual_interest_rate=str(q_rate(annual_interest_rate)),
        day_count_basis=day_count_basis,
        current_balance=str(q(Decimal("0"))),
        accrued_interest=str(q(Decimal("0"))),
        last_accrual_date=opened_on,
    )
    db.add(acct)
    db.flush()

    append_event(
        db,
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=acct.id,
        event_type="DEPOSIT_ACCOUNT_OPENED",
        payload={
            "opened_on": opened_on.isoformat(),
            "annual_interest_rate": str(q_rate(annual_interest_rate)),
            "day_count_basis": day_count_basis,
        },
        event_time=utcnow(),
        idempotency_key=idempotency_key,
    )
    return acct


def post_deposit(
    db: Session,
    *,
    account_id: str,
    amount: Decimal,
    effective_date: dt.date,
    idempotency_key: str | None,
) -> DepositAccount:
    acct = db.get(DepositAccount, account_id)
    if not acct:
        raise ValueError("account_not_found")

    if idempotency_key:
        existing = find_event_by_idempotency_key(
            db,
            aggregate_type=AGGREGATE_TYPE,
            idempotency_key=idempotency_key,
        )
        if existing and existing.event_type == "DEPOSIT_POSTED" and existing.aggregate_id == account_id:
            return acct

    amt = q(amount)
    new_balance = q(_dec(acct.current_balance) + amt)
    acct.current_balance = str(new_balance)

    txn_id = f"deposit:{idempotency_key or utcnow().isoformat()}"
    db.add(
        LedgerEntry(
            effective_date=effective_date,
            account_type=AGGREGATE_TYPE,
            account_id=account_id,
            txn_id=txn_id,
            description="Customer deposit",
            debit_account="cash",
            credit_account="customer_deposits",
            amount=str(amt),
        )
    )

    append_event(
        db,
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=account_id,
        event_type="DEPOSIT_POSTED",
        payload={"amount": str(amt), "effective_date": effective_date.isoformat()},
        event_time=utcnow(),
        idempotency_key=idempotency_key,
    )
    return acct


def post_withdrawal(
    db: Session,
    *,
    account_id: str,
    amount: Decimal,
    effective_date: dt.date,
    idempotency_key: str | None,
) -> DepositAccount:
    acct = db.get(DepositAccount, account_id)
    if not acct:
        raise ValueError("account_not_found")

    if idempotency_key:
        existing = find_event_by_idempotency_key(
            db,
            aggregate_type=AGGREGATE_TYPE,
            idempotency_key=idempotency_key,
        )
        if existing and existing.event_type == "WITHDRAWAL_POSTED" and existing.aggregate_id == account_id:
            return acct

    amt = q(amount)
    if _dec(acct.current_balance) < amt:
        raise ValueError("insufficient_funds")

    new_balance = q(_dec(acct.current_balance) - amt)
    acct.current_balance = str(new_balance)

    txn_id = f"withdrawal:{idempotency_key or utcnow().isoformat()}"
    db.add(
        LedgerEntry(
            effective_date=effective_date,
            account_type=AGGREGATE_TYPE,
            account_id=account_id,
            txn_id=txn_id,
            description="Customer withdrawal",
            debit_account="customer_deposits",
            credit_account="cash",
            amount=str(amt),
        )
    )

    append_event(
        db,
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=account_id,
        event_type="WITHDRAWAL_POSTED",
        payload={"amount": str(amt), "effective_date": effective_date.isoformat()},
        event_time=utcnow(),
        idempotency_key=idempotency_key,
    )
    return acct


def accrue_interest(
    db: Session,
    *,
    account_id: str,
    as_of_date: dt.date,
) -> DepositAccount:
    acct = db.get(DepositAccount, account_id)
    if not acct:
        raise ValueError("account_not_found")

    start_date = acct.last_accrual_date or acct.opened_on
    if as_of_date <= start_date:
        return acct

    days = (as_of_date - start_date).days
    rate = _dec(acct.annual_interest_rate)
    balance = _dec(acct.current_balance)

    interest = q(balance * rate * Decimal(days) / Decimal(acct.day_count_basis))
    acct.accrued_interest = str(q(_dec(acct.accrued_interest) + interest))
    acct.last_accrual_date = as_of_date

    append_event(
        db,
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=account_id,
        event_type="INTEREST_ACCRUED",
        payload={
            "from_date": start_date.isoformat(),
            "to_date": as_of_date.isoformat(),
            "days": days,
            "interest": str(interest),
        },
        event_time=utcnow(),
        idempotency_key=None,
    )
    return acct


def apply_month_end(
    db: Session,
    *,
    account_id: str,
    effective_date: dt.date,
) -> DepositAccount:
    acct = db.get(DepositAccount, account_id)
    if not acct:
        raise ValueError("account_not_found")

    accrued = q(_dec(acct.accrued_interest))
    if accrued == Decimal("0.00"):
        return acct

    acct.current_balance = str(q(_dec(acct.current_balance) + accrued))
    acct.accrued_interest = str(q(Decimal("0")))

    txn_id = f"interest_post:{effective_date.isoformat()}:{account_id}"
    db.add(
        LedgerEntry(
            effective_date=effective_date,
            account_type=AGGREGATE_TYPE,
            account_id=account_id,
            txn_id=txn_id,
            description="Month-end interest posting",
            debit_account="interest_expense",
            credit_account="customer_deposits",
            amount=str(accrued),
        )
    )

    append_event(
        db,
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=account_id,
        event_type="MONTH_END_APPLIED",
        payload={"effective_date": effective_date.isoformat(), "interest_posted": str(accrued)},
        event_time=utcnow(),
        idempotency_key=None,
    )
    return acct
