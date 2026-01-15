from decimal import Decimal
import datetime as dt

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DepositAccount, OutboxMessage, QueueMessage, WebhookSubscription
from app.schemas import (
    AccrueInterestRequest,
    ApplyMonthEndRequest,
    DepositAccountOpenRequest,
    DepositAccountResponse,
    DispatchOutboxRequest,
    MoneyRequest,
    OutboxReplayRequest,
    LoanAccountOpenRequest,
    LoanAccountResponse,
    WebhookSubscriptionCreateRequest,
    WebhookSubscriptionResponse,
)
from app.services.deposit import apply_month_end, accrue_interest, open_account, post_deposit, post_withdrawal
from app.models import LoanAccount
from app.services.loan import accrue_interest as loan_accrue_interest
from app.services.loan import open_loan, post_repayment
from app.time import utcnow


router = APIRouter()


def _dec(s: str) -> Decimal:
    return Decimal(s)


def _deposit_response(acct: DepositAccount) -> DepositAccountResponse:
    return DepositAccountResponse(
        id=acct.id,
        opened_on=acct.opened_on,
        status=acct.status,
        annual_interest_rate=_dec(acct.annual_interest_rate),
        day_count_basis=acct.day_count_basis,
        current_balance=_dec(acct.current_balance),
        accrued_interest=_dec(acct.accrued_interest),
    )


def _loan_response(acct: LoanAccount) -> LoanAccountResponse:
    return LoanAccountResponse(
        id=acct.id,
        opened_on=acct.opened_on,
        status=acct.status,
        principal=_dec(acct.principal),
        annual_interest_rate=_dec(acct.annual_interest_rate),
        day_count_basis=acct.day_count_basis,
        outstanding_principal=_dec(acct.outstanding_principal),
        accrued_interest=_dec(acct.accrued_interest),
    )


@router.post("/deposit/accounts", response_model=DepositAccountResponse)
def create_deposit_account(req: DepositAccountOpenRequest, db: Session = Depends(get_db)):
    acct = open_account(
        db,
        opened_on=req.opened_on,
        annual_interest_rate=req.annual_interest_rate,
        day_count_basis=req.day_count_basis,
        idempotency_key=req.idempotency_key,
    )
    db.commit()
    db.refresh(acct)
    return _deposit_response(acct)


@router.get("/deposit/accounts/{account_id}", response_model=DepositAccountResponse)
def get_deposit_account(account_id: str, db: Session = Depends(get_db)):
    acct = db.get(DepositAccount, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="account_not_found")
    return _deposit_response(acct)


@router.post("/deposit/accounts/{account_id}/deposit", response_model=DepositAccountResponse)
def deposit(account_id: str, req: MoneyRequest, db: Session = Depends(get_db)):
    try:
        acct = post_deposit(
            db,
            account_id=account_id,
            amount=req.amount,
            effective_date=req.effective_date,
            idempotency_key=req.idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(acct)
    return _deposit_response(acct)


@router.post("/deposit/accounts/{account_id}/withdraw", response_model=DepositAccountResponse)
def withdraw(account_id: str, req: MoneyRequest, db: Session = Depends(get_db)):
    try:
        acct = post_withdrawal(
            db,
            account_id=account_id,
            amount=req.amount,
            effective_date=req.effective_date,
            idempotency_key=req.idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(acct)
    return _deposit_response(acct)


@router.post("/deposit/accounts/{account_id}/accrue", response_model=DepositAccountResponse)
def accrue(account_id: str, req: AccrueInterestRequest, db: Session = Depends(get_db)):
    try:
        acct = accrue_interest(db, account_id=account_id, as_of_date=req.as_of_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(acct)
    return _deposit_response(acct)


@router.post("/deposit/accounts/{account_id}/month-end", response_model=DepositAccountResponse)
def month_end(account_id: str, req: ApplyMonthEndRequest, db: Session = Depends(get_db)):
    try:
        acct = apply_month_end(db, account_id=account_id, effective_date=req.effective_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(acct)
    return _deposit_response(acct)


@router.post("/webhooks/subscriptions", response_model=WebhookSubscriptionResponse)
def create_webhook_subscription(req: WebhookSubscriptionCreateRequest, db: Session = Depends(get_db)):
    sub = WebhookSubscription(target_url=req.target_url, enabled=True)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return WebhookSubscriptionResponse(id=sub.id, target_url=sub.target_url, enabled=sub.enabled)


@router.post("/loan/accounts", response_model=LoanAccountResponse)
def create_loan_account(req: LoanAccountOpenRequest, db: Session = Depends(get_db)):
    acct = open_loan(
        db,
        opened_on=req.opened_on,
        principal=req.principal,
        annual_interest_rate=req.annual_interest_rate,
        day_count_basis=req.day_count_basis,
        idempotency_key=req.idempotency_key,
    )
    db.commit()
    db.refresh(acct)
    return _loan_response(acct)


@router.get("/loan/accounts/{account_id}", response_model=LoanAccountResponse)
def get_loan_account(account_id: str, db: Session = Depends(get_db)):
    acct = db.get(LoanAccount, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="account_not_found")
    return _loan_response(acct)


@router.post("/loan/accounts/{account_id}/accrue", response_model=LoanAccountResponse)
def loan_accrue(account_id: str, req: AccrueInterestRequest, db: Session = Depends(get_db)):
    try:
        acct = loan_accrue_interest(db, account_id=account_id, as_of_date=req.as_of_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(acct)
    return _loan_response(acct)


@router.post("/loan/accounts/{account_id}/repay", response_model=LoanAccountResponse)
def loan_repay(account_id: str, req: MoneyRequest, db: Session = Depends(get_db)):
    try:
        acct = post_repayment(
            db,
            account_id=account_id,
            amount=req.amount,
            effective_date=req.effective_date,
            idempotency_key=req.idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(acct)
    return _loan_response(acct)


@router.post("/outbox/dispatch")
def dispatch_outbox(req: DispatchOutboxRequest, db: Session = Depends(get_db)):
    now = utcnow()
    pending = (
        db.query(OutboxMessage)
        .filter(OutboxMessage.status == "PENDING")
        .filter(or_(OutboxMessage.next_attempt_at.is_(None), OutboxMessage.next_attempt_at <= now))
        .order_by(OutboxMessage.created_at.asc())
        .limit(req.max_messages)
        .all()
    )

    results: list[dict] = []
    for msg in pending:
        if msg.attempts >= msg.max_attempts:
            msg.status = "DEAD"
            results.append({"id": msg.id, "destination": msg.destination, "status": "DEAD"})
            continue

        msg.attempts += 1
        try:
            if msg.destination.startswith("queue:"):
                db.add(
                    QueueMessage(
                        topic=msg.destination.split(":", 1)[1],
                        payload={
                            "event_id": msg.event.id,
                            "aggregate_type": msg.event.aggregate_type,
                            "aggregate_id": msg.event.aggregate_id,
                            "event_type": msg.event.event_type,
                            "event_time": msg.event.event_time.isoformat(),
                            "payload": msg.event.payload,
                        },
                    )
                )
                msg.status = "SENT"
                msg.last_error = None
                msg.next_attempt_at = None
                results.append({"id": msg.id, "destination": msg.destination, "status": "SENT"})

            elif msg.destination.startswith("webhook:"):
                sub_id = msg.destination.split(":", 1)[1]
                sub = db.get(WebhookSubscription, sub_id)
                if not sub or not sub.enabled:
                    msg.status = "SKIPPED"
                    msg.last_error = "subscription_disabled_or_missing"
                    results.append({"id": msg.id, "destination": msg.destination, "status": "SKIPPED"})
                else:
                    body = {
                        "event_id": msg.event.id,
                        "aggregate_type": msg.event.aggregate_type,
                        "aggregate_id": msg.event.aggregate_id,
                        "event_type": msg.event.event_type,
                        "event_time": msg.event.event_time.isoformat(),
                        "payload": msg.event.payload,
                    }
                    with httpx.Client(timeout=5.0) as client:
                        r = client.post(sub.target_url, json=body)
                        r.raise_for_status()

                    msg.status = "SENT"
                    msg.last_error = None
                    msg.next_attempt_at = None
                    results.append({"id": msg.id, "destination": msg.destination, "status": "SENT"})
            else:
                msg.status = "FAILED"
                msg.last_error = f"unknown_destination:{msg.destination}"
                results.append({"id": msg.id, "destination": msg.destination, "status": "FAILED"})

        except Exception as e:
            msg.last_error = str(e)
            if msg.attempts >= msg.max_attempts:
                msg.status = "DEAD"
                msg.next_attempt_at = None
                results.append({"id": msg.id, "destination": msg.destination, "status": "DEAD", "error": str(e)})
            else:
                backoff_seconds = min(300, 2 ** (msg.attempts - 1))
                msg.status = "PENDING"
                msg.next_attempt_at = now + dt.timedelta(seconds=backoff_seconds)
                results.append(
                    {
                        "id": msg.id,
                        "destination": msg.destination,
                        "status": "RETRY",
                        "error": str(e),
                        "next_attempt_at": msg.next_attempt_at.isoformat(),
                    }
                )

    db.commit()
    return {"processed": len(results), "results": results}


@router.post("/outbox/replay")
def replay_outbox(req: OutboxReplayRequest, db: Session = Depends(get_db)):
    q = db.query(OutboxMessage).join(OutboxMessage.event)

    if req.aggregate_type is not None:
        q = q.filter(OutboxMessage.event.has(aggregate_type=req.aggregate_type))
    if req.aggregate_id is not None:
        q = q.filter(OutboxMessage.event.has(aggregate_id=req.aggregate_id))
    if req.destination is not None:
        q = q.filter(OutboxMessage.destination == req.destination)

    updated = 0
    for msg in q.all():
        msg.status = "PENDING"
        msg.attempts = 0
        msg.last_error = None
        msg.next_attempt_at = utcnow()
        updated += 1

    db.commit()
    return {"updated": updated}
