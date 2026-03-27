import pytest

from shop_backend.services.auth_service import authenticate_user
from shop_backend.security.tokens import decode_access_token


def test_authenticate_returns_token(db, regular_user):
    token = authenticate_user(db, "user1", "userpass")
    payload = decode_access_token(token)
    assert payload["sub"] == str(regular_user.id)
    assert payload["role"] == "user"


def test_authenticate_wrong_password_raises(db, regular_user):
    with pytest.raises(ValueError, match="Invalid credentials"):
        authenticate_user(db, "user1", "wrongpass")


def test_authenticate_unknown_user_raises(db):
    with pytest.raises(ValueError, match="Invalid credentials"):
        authenticate_user(db, "nobody", "pass")
