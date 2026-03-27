import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shop_backend.db.base import Base
from shop_backend.db.models import User, UserRole
from shop_backend.security.password import hash_password


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def admin_user(db):
    user = User(
        username="admin",
        email="admin@example.com",
        password_hash=hash_password("adminpass"),
        role=UserRole.admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def regular_user(db):
    user = User(
        username="user1",
        email="user1@example.com",
        password_hash=hash_password("userpass"),
        role=UserRole.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
