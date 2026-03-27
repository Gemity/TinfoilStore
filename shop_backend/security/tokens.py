from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import jwt, JWTError

from shop_backend.config import settings

ALGORITHM = "HS256"


def create_access_token(user_id: UUID, role: str) -> str:
    expire = datetime.now(tz=timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_TTL_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
