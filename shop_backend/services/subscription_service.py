import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from shop_backend.db.models import (
    Subscription, SubscriptionEvent, SubscriptionEventType, SubscriptionStatus, User
)


def _effective_status(sub: Subscription) -> str:
    if sub.status == SubscriptionStatus.revoked:
        return "revoked"
    now = datetime.now(tz=timezone.utc)
    # Ensure timezone-aware comparison
    starts = sub.starts_at if sub.starts_at.tzinfo else sub.starts_at.replace(tzinfo=timezone.utc)
    ends = sub.ends_at if sub.ends_at.tzinfo else sub.ends_at.replace(tzinfo=timezone.utc)
    if ends < now:
        return "expired"
    if starts <= now:
        return "active"
    return "pending"


def get_effective_status(sub: Subscription) -> str:
    return _effective_status(sub)


def get_active_subscription(db: Session, user_id: uuid.UUID) -> Subscription | None:
    subs = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
        .all()
    )
    for sub in subs:
        if _effective_status(sub) == "active":
            return sub
    return None


def grant_subscription(
    db: Session, user_id: uuid.UUID, days: int, actor_id: uuid.UUID,
    hours: int = 0, minutes: int = 0,
) -> Subscription:
    now = datetime.now(tz=timezone.utc)
    duration = timedelta(days=days, hours=hours, minutes=minutes)
    if duration.total_seconds() <= 0:
        raise ValueError("Duration must be greater than 0")
    sub = Subscription(
        user_id=user_id,
        status=SubscriptionStatus.active,
        starts_at=now,
        ends_at=now + duration,
    )
    db.add(sub)
    db.flush()
    event = SubscriptionEvent(
        subscription_id=sub.id,
        event_type=SubscriptionEventType.granted,
        effective_at=now,
        delta_days=days,
        actor_user_id=actor_id,
    )
    db.add(event)
    db.commit()
    db.refresh(sub)
    return sub


def extend_subscription(
    db: Session, user_id: uuid.UUID, days: int, notes: str, actor_id: uuid.UUID,
    hours: int = 0, minutes: int = 0,
) -> Subscription:
    sub = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if not sub:
        raise ValueError(f"No subscription found for user {user_id}")
    if sub.status == SubscriptionStatus.revoked:
        raise ValueError("Cannot extend a revoked subscription")

    duration = timedelta(days=days, hours=hours, minutes=minutes)
    if duration.total_seconds() <= 0:
        raise ValueError("Duration must be greater than 0")

    now = datetime.now(tz=timezone.utc)
    sub.ends_at = sub.ends_at + duration
    if sub.status == SubscriptionStatus.expired or _effective_status(sub) != "active":
        sub.status = SubscriptionStatus.active

    event = SubscriptionEvent(
        subscription_id=sub.id,
        event_type=SubscriptionEventType.manual_extension,
        effective_at=now,
        delta_days=days,
        notes=notes,
        actor_user_id=actor_id,
    )
    db.add(event)
    db.commit()
    db.refresh(sub)
    return sub


def revoke_subscription(
    db: Session, user_id: uuid.UUID, reason: str, actor_id: uuid.UUID
) -> Subscription:
    sub = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if not sub:
        raise ValueError(f"No subscription found for user {user_id}")

    now = datetime.now(tz=timezone.utc)
    sub.status = SubscriptionStatus.revoked
    sub.revoked_at = now
    sub.revoked_reason = reason

    event = SubscriptionEvent(
        subscription_id=sub.id,
        event_type=SubscriptionEventType.revoked,
        effective_at=now,
        notes=reason,
        actor_user_id=actor_id,
    )
    db.add(event)
    db.commit()
    db.refresh(sub)
    return sub
