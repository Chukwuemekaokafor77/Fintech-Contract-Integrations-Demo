import datetime as dt
from sqlalchemy.orm import Session

from app.models import DomainEvent, OutboxMessage, WebhookSubscription
from app.time import utcnow


def append_event(
    db: Session,
    *,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    payload: dict,
    event_time: dt.datetime,
    idempotency_key: str | None,
) -> DomainEvent:
    event = DomainEvent(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=payload,
        event_time=event_time,
        idempotency_key=idempotency_key,
    )
    db.add(event)
    db.flush()

    subs = (
        db.query(WebhookSubscription)
        .filter(WebhookSubscription.enabled.is_(True))
        .all()
    )
    for sub in subs:
        db.add(
            OutboxMessage(
                event_id=event.id,
                destination=f"webhook:{sub.id}",
                next_attempt_at=utcnow(),
            )
        )

    db.add(OutboxMessage(event_id=event.id, destination="queue:domain_events", next_attempt_at=utcnow()))
    return event


def find_event_by_idempotency_key(
    db: Session,
    *,
    aggregate_type: str,
    idempotency_key: str,
) -> DomainEvent | None:
    return (
        db.query(DomainEvent)
        .filter(DomainEvent.aggregate_type == aggregate_type)
        .filter(DomainEvent.idempotency_key == idempotency_key)
        .order_by(DomainEvent.created_at.desc())
        .first()
    )
