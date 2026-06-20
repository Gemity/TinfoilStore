import pytest

from shop_backend.db.models import User, UserRole
from shop_backend.security.password import verify_password
from shop_backend.services import admin_account_service as svc
from shop_backend.services.admin_account_service import AdminAccountError


def _make_admin(db, username, email, password="adminpass"):
    return svc.create_admin(db, username, email, password)


def test_create_admin_sets_role_and_hash(db):
    user = _make_admin(db, "boss", "boss@example.com", "secret123")
    assert user.role == UserRole.admin
    assert user.is_active is True
    assert verify_password("secret123", user.password_hash)


def test_create_admin_rejects_duplicate_username(db, admin_user):
    with pytest.raises(AdminAccountError, match="Username already exists"):
        _make_admin(db, "admin", "other@example.com")


def test_create_admin_rejects_duplicate_email(db, admin_user):
    with pytest.raises(AdminAccountError, match="Email already exists"):
        _make_admin(db, "admin2", "admin@example.com")


def test_list_admins_excludes_regular_users(db, admin_user, regular_user):
    admins = svc.list_admins(db)
    names = {a.username for a in admins}
    assert "admin" in names
    assert "user1" not in names


def test_list_admins_partial_search(db, admin_user):
    _make_admin(db, "support_bob", "bob@example.com")
    found = svc.list_admins(db, "bob")
    assert [a.username for a in found] == ["support_bob"]


def test_set_admin_password_changes_hash(db, admin_user):
    old_hash = admin_user.password_hash
    updated = svc.set_admin_password(db, "admin", "newpass123")
    assert updated.password_hash != old_hash
    assert verify_password("newpass123", updated.password_hash)


def test_set_password_unknown_admin_raises(db):
    with pytest.raises(LookupError):
        svc.set_admin_password(db, "ghost", "whatever123")


def test_delete_last_active_admin_blocked(db, admin_user):
    with pytest.raises(AdminAccountError, match="last active admin"):
        svc.delete_admin(db, "admin")
    # still there
    assert svc.get_admin(db, "admin").username == "admin"


def test_delete_admin_when_another_active_exists(db, admin_user):
    _make_admin(db, "admin2", "admin2@example.com")
    svc.delete_admin(db, "admin")
    with pytest.raises(LookupError):
        svc.get_admin(db, "admin")
    assert svc.get_admin(db, "admin2").username == "admin2"


def test_delete_inactive_admin_allowed_even_if_only_one_active(db, admin_user):
    # second admin, but inactive
    extra = _make_admin(db, "old_admin", "old@example.com")
    extra.is_active = False
    db.commit()
    # deleting the inactive one is fine; the single active admin remains
    svc.delete_admin(db, "old_admin")
    with pytest.raises(LookupError):
        svc.get_admin(db, "old_admin")


def test_delete_admin_nulls_subscription_event_actor(db, admin_user, regular_user):
    from shop_backend.services.subscription_service import grant_subscription
    from shop_backend.db.models import SubscriptionEvent

    _make_admin(db, "admin2", "admin2@example.com")
    grant_subscription(db, regular_user.id, 30, admin_user.id)
    # admin_user is the actor on an event; deleting must not violate FK
    svc.delete_admin(db, "admin")
    remaining = db.query(SubscriptionEvent).all()
    assert remaining  # event still exists
    assert all(e.actor_user_id is None for e in remaining)
