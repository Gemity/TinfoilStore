from shop_backend.db.models import ContentObject
from shop_backend.services.shop_service import build_shop_index
from shop_backend.services.subscription_service import grant_subscription


def test_shop_index_uses_request_base_url_without_referrer(db, regular_user, admin_user):
    obj = ContentObject(
        title="Test Game [0100000000000000].nsp",
        storage_key="games/test.nsp",
        is_protected=True,
        is_enabled=True,
    )
    db.add(obj)
    db.commit()
    grant_subscription(db, regular_user.id, 30, admin_user.id)

    payload = build_shop_index(db, regular_user.id, base_url="http://160.187.229.43")

    assert "referrer" not in payload
    assert payload["directories"] == []
    assert payload["files"][0]["url"].startswith("http://160.187.229.43/shop/download/")
