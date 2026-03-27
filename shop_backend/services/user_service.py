import uuid

from sqlalchemy.orm import Session

from shop_backend.db.models import User, UserRole
from shop_backend.schemas.users import UserCreate
from shop_backend.security.password import hash_password


def create_user(db: Session, data: UserCreate) -> User:
    if db.query(User).filter(User.username == data.username).first():
        raise ValueError(f"Username '{data.username}' already exists")
    if db.query(User).filter(User.email == data.email).first():
        raise ValueError(f"Email '{data.email}' already exists")
    role = UserRole(data.role) if data.role in UserRole._value2member_map_ else UserRole.user
    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User {user_id} not found")
    return user
