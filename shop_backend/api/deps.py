import uuid
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
from sqlalchemy.orm import Session

from shop_backend.db.models import User, UserRole
from shop_backend.db.session import get_db
from shop_backend.security.password import verify_password
from shop_backend.security.tokens import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)
basic_scheme = HTTPBasic(auto_error=False)


def get_current_user(
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    basic_creds: Optional[HTTPBasicCredentials] = Depends(basic_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate via Bearer token OR Basic Auth (username/password)."""

    # Try Bearer token first
    if bearer_creds:
        try:
            payload = decode_access_token(bearer_creds.credentials)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user_id = uuid.UUID(payload["sub"])
        user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
        return user

    # Try Basic Auth
    if basic_creds:
        user = (
            db.query(User)
            .filter(User.username == basic_creds.username, User.is_active.is_(True))
            .first()
        )
        if user and verify_password(basic_creds.password, user.password_hash):
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    # No credentials provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Use Bearer token or Basic Auth (username/password).",
    )


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
