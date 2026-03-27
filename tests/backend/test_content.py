import uuid
from unittest.mock import patch

import pytest

from shop_backend.db.models import ContentObject
from shop_backend.services.content_service import list_content, get_download_url
from shop_backend.services.subscription_service import grant_subscription


def _add_content(db, protected: bool = True) -> ContentObject:
    obj = ContentObject(
        title="Test Game",
        storage_key="games/test.nsp",
        is_protected=protected,
        is_enabled=True,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def test_list_content_denied_without_subscription(db, regular_user):
    _add_content(db)
    with pytest.raises(PermissionError):
        list_content(db, regular_user.id)


def test_list_content_allowed_with_active_subscription(db, regular_user, admin_user):
    _add_content(db)
    grant_subscription(db, regular_user.id, 30, admin_user.id)
    items = list_content(db, regular_user.id)
    assert len(items) >= 1


def test_download_denied_without_subscription(db, regular_user):
    obj = _add_content(db)
    with pytest.raises(PermissionError):
        get_download_url(db, regular_user.id, obj.id)


def test_download_returns_presigned_url(db, regular_user, admin_user):
    obj = _add_content(db, protected=True)
    grant_subscription(db, regular_user.id, 30, admin_user.id)
    fake_url = "https://s3.wasabisys.com/bucket/games/test.nsp?X-Amz-Signature=abc"
    with patch("shop_backend.services.content_service.generate_presigned_url", return_value=fake_url):
        _, url = get_download_url(db, regular_user.id, obj.id)
    assert url == fake_url


def test_download_unprotected_content_no_presign(db, regular_user, admin_user):
    obj = _add_content(db, protected=False)
    grant_subscription(db, regular_user.id, 30, admin_user.id)
    _, url = get_download_url(db, regular_user.id, obj.id)
    assert "games/test.nsp" in url


def test_download_missing_content_raises(db, regular_user, admin_user):
    grant_subscription(db, regular_user.id, 30, admin_user.id)
    with pytest.raises(LookupError):
        get_download_url(db, regular_user.id, uuid.uuid4())
