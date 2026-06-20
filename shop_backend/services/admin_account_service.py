"""Manage admin login accounts (the DB users that sign in to the /docs admin panel).

This is intentionally separate from ftp_user_service: FTP users are OS accounts for
customer FTP logins, while admins are pure DB users distinguished by role=admin.
"""

from sqlalchemy.orm import Session

from shop_backend.db.models import SubscriptionEvent, User, UserRole
from shop_backend.security.password import hash_password


class AdminAccountError(ValueError):
    pass


def list_admins(db: Session, username_filter: str = "") -> list[User]:
    admins = (
        db.query(User)
        .filter(User.role == UserRole.admin)
        .order_by(User.username)
        .all()
    )
    if username_filter:
        needle = username_filter.casefold()
        admins = [a for a in admins if needle in a.username.casefold()]
    return admins


def get_admin(db: Session, username: str) -> User:
    user = (
        db.query(User)
        .filter(User.username == username, User.role == UserRole.admin)
        .first()
    )
    if not user:
        raise LookupError("Admin not found")
    return user


def create_admin(db: Session, username: str, email: str, password: str) -> User:
    username = username.strip()
    email = email.strip()
    if db.query(User).filter(User.username == username).first():
        raise AdminAccountError("Username already exists")
    if db.query(User).filter(User.email == email).first():
        raise AdminAccountError("Email already exists")

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_admin_password(db: Session, username: str, password: str) -> User:
    user = get_admin(db, username)
    user.password_hash = hash_password(password)
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


def _active_admin_count(db: Session) -> int:
    return (
        db.query(User)
        .filter(User.role == UserRole.admin, User.is_active.is_(True))
        .count()
    )


def delete_admin(db: Session, username: str) -> None:
    """Hard-delete an admin. Refuses to delete the last active admin to avoid lockout."""
    user = get_admin(db, username)
    if user.is_active and _active_admin_count(db) <= 1:
        raise AdminAccountError("Cannot delete the last active admin")

    # Subscription events may reference this admin as the actor (nullable FK).
    # Null those references so the delete does not violate the foreign key.
    db.query(SubscriptionEvent).filter(
        SubscriptionEvent.actor_user_id == user.id
    ).update({SubscriptionEvent.actor_user_id: None}, synchronize_session=False)

    db.delete(user)
    db.commit()
