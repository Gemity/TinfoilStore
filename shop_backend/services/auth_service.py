from sqlalchemy.orm import Session

from shop_backend.db.models import User
from shop_backend.security.password import verify_password
from shop_backend.security.tokens import create_access_token


def authenticate_user(db: Session, username: str, password: str) -> str:
    user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Invalid credentials")
    return create_access_token(user.id, user.role.value)
