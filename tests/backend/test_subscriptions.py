import uuid
from datetime import datetime, timedelta, timezone

import pytest

from shop_backend.db.models import Subscription, SubscriptionStatus
from shop_backend.services.subscription_service import (
    extend_subscription,
    get_active_subscription,
    get_effective_status,
    grant_subscription,
    revoke_subscription,
)


def test_grant_creates_active_subscription(db, regular_user, admin_user):
    sub = grant_subscription(db, regular_user.id, 30, admin_user.id)
    assert sub.status == SubscriptionStatus.active
    assert get_effective_status(sub) == "active"


def test_get_active_subscription_returns_valid(db, regular_user, admin_user):
    grant_subscription(db, regular_user.id, 30, admin_user.id)
    active = get_active_subscription(db, regular_user.id)
    assert active is not None


def test_expired_subscription_not_returned_as_active(db, regular_user, admin_user):
    sub = grant_subscription(db, regular_user.id, 1, admin_user.id)
    # Force ends_at into the past
    sub.ends_at = datetime.now(tz=timezone.utc) - timedelta(days=2)
    db.commit()
    active = get_active_subscription(db, regular_user.id)
    assert active is None


def test_effective_status_expired(db, regular_user, admin_user):
    sub = grant_subscription(db, regular_user.id, 1, admin_user.id)
    sub.ends_at = datetime.now(tz=timezone.utc) - timedelta(days=1)
    db.commit()
    assert get_effective_status(sub) == "expired"


def test_effective_status_revoked(db, regular_user, admin_user):
    grant_subscription(db, regular_user.id, 30, admin_user.id)
    sub = revoke_subscription(db, regular_user.id, "violated tos", admin_user.id)
    assert get_effective_status(sub) == "revoked"


def test_extend_subscription_adds_days(db, regular_user, admin_user):
    sub = grant_subscription(db, regular_user.id, 30, admin_user.id)
    original_end = sub.ends_at
    extended = extend_subscription(db, regular_user.id, 10, "loyalty bonus", admin_user.id)
    assert extended.ends_at > original_end
    assert get_effective_status(extended) == "active"


def test_extend_records_event(db, regular_user, admin_user):
    grant_subscription(db, regular_user.id, 30, admin_user.id)
    sub = extend_subscription(db, regular_user.id, 7, "promo", admin_user.id)
    events = [e for e in sub.events if e.event_type.value == "manual_extension"]
    assert len(events) == 1
    assert events[0].delta_days == 7
    assert events[0].notes == "promo"


def test_revoke_prevents_active_lookup(db, regular_user, admin_user):
    grant_subscription(db, regular_user.id, 30, admin_user.id)
    revoke_subscription(db, regular_user.id, "abuse", admin_user.id)
    active = get_active_subscription(db, regular_user.id)
    assert active is None


def test_extend_revoked_raises(db, regular_user, admin_user):
    grant_subscription(db, regular_user.id, 30, admin_user.id)
    revoke_subscription(db, regular_user.id, "ban", admin_user.id)
    with pytest.raises(ValueError, match="revoked"):
        extend_subscription(db, regular_user.id, 10, "", admin_user.id)
