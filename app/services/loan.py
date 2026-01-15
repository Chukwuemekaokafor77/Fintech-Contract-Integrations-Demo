import datetime as dt
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import LedgerEntry, LoanAccount
from app.money import q, q_rate
from app.services.events import append_event, find_event_by_idempotency_key
from app.time import utcnow


AGGREGATE_TYPE = "loan_account"


def _dec(s: str) -> Decimal:
    return Decimal(s)


def open_loan(
    db: Session,
    *,
    opened_on: dt.date,
    principal: Decimal,
    annual_interest_rate: Decimal,
    day_count_basis: int,
    idempotency_key: str | None,
) -> LoanAccount:
    if idempotency_key:
        existing = find_event_by_idempotency_key(
            db,
            aggregate_type=AGGREGATE_TYPE,
            idempotency_key=idempotency_key,
        )
        if existing and existing.event_type == "LOAN_OPENED":
            acct = db.get(LoanAccount, existing.aggregate_id)
            if acct:
                return acct

    p = q(principal)
    acct = LoanAccount(
        opened_on=opened_on,
        principal=str(p),
        annual_interest_rate=str(q_rate(annual_interest_rate)),
        day_count_basis=day_count_basis,
        outstanding_principal=str(p),
        accrued_interest=str(q(Decimal("0"))),
        last_accrual_date=opened_on,
    )
    db.add(acct)
    db.flush()

    txn_id = f"loan_disburse:{idempotency_key or utcnow().isoformat()}"
    db.add(
        LedgerEntry(
            effective_date=opened_on,
            account_type=AGGREGATE_TYPE,
            account_id=acct.id,
            txn_id=txn_id,
            description="Loan disbursement",
            debit_account="loan_receivable",
            credit_account="cash",
            amount=str(p),
        )
    )

    append_event(
        db,
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=acct.id,
        event_type="LOAN_OPENED",
        payload={
            "opened_on": opened_on.isoformat(),
            "principal": str(p),
            "annual_interest_rate": str(q_rate(annual_interest_rate)),
            "day_count_basis": day_count_basis,
        },
        event_time=utcnow(),
        idempotency_key=idempotency_key,
    )
    return acct


def accrue_interest(db: Session, *, account_id: str, as_of_date: dt.date) -> LoanAccount:
    acct = db.get(LoanAccount, account_id)
    if not acct:
        raise ValueError("account_not_found")

    start_date = acct.last_accrual_date or acct.opened_on
    if as_of_date <= start_date:
        return acct

    days = (as_of_date - start_date).days
    rate = _dec(acct.annual_interest_rate)
    principal = _dec(acct.outstanding_principal)

    interest = q(principal * rate * Decimal(days) / Decimal(acct.day_count_basis))
    acct.accrued_interest = str(q(_dec(acct.accrued_interest) + interest))
    acct.last_accrual_date = as_of_date

    append_event(
        db,
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=account_id,
        event_type="LOAN_INTEREST_ACCRUED",
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


def post_repayment(
    db: Session,
    *,
    account_id: str,
    amount: Decimal,
    effective_date: dt.date,
    idempotency_key: str | None,
) -> LoanAccount:
    acct = db.get(LoanAccount, account_id)
    if not acct:
        raise ValueError("account_not_found")

    if idempotency_key:
        existing = find_event_by_idempotency_key(
            db,
            aggregate_type=AGGREGATE_TYPE,
            idempotency_key=idempotency_key,
        )
        if existing and existing.event_type == "LOAN_REPAYMENT_POSTED" and existing.aggregate_id == account_id:
            return acct

    amt = q(amount)
    interest_due = q(_dec(acct.accrued_interest))
    principal_due = q(_dec(acct.outstanding_principal))

    pay_interest = min(amt, interest_due)
    remaining = q(amt - pay_interest)
    pay_principal = min(remaining, principal_due)

    acct.accrued_interest = str(q(interest_due - pay_interest))
    acct.outstanding_principal = str(q(principal_due - pay_principal))

    txn_base = idempotency_key or utcnow().isoformat()
    if pay_interest > Decimal("0.00"):
        db.add(
            LedgerEntry(
                effective_date=effective_date,
                account_type=AGGREGATE_TYPE,
                account_id=account_id,
                txn_id=f"loan_payment_interest:{txn_base}",
                description="Loan payment (interest)",
                debit_account="cash",
                credit_account="interest_income",
                amount=str(pay_interest),
            )
        )

    if pay_principal > Decimal("0.00"):
        db.add(
            LedgerEntry(
                effective_date=effective_date,
                account_type=AGGREGATE_TYPE,
                account_id=account_id,
                txn_id=f"loan_payment_principal:{txn_base}",
                description="Loan payment (principal)",
                debit_account="cash",
                credit_account="loan_receivable",
                amount=str(pay_principal),
            )
        )

    append_event(
        db,
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=account_id,
        event_type="LOAN_REPAYMENT_POSTED",
        payload={
            "amount": str(amt),
            "interest_paid": str(pay_interest),
            "principal_paid": str(pay_principal),
            "effective_date": effective_date.isoformat(),
        },
        event_time=utcnow(),
        idempotency_key=idempotency_key,
    )

    return acct
