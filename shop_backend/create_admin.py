"""One-time script to create the first admin user.

Usage (interactive):
    python -m shop_backend.create_admin

Usage (command line):
    python -m shop_backend.create_admin --username admin --email admin@example.com --password secret123
"""

import argparse
import getpass
import sys

from shop_backend.db.session import SessionLocal
from shop_backend.db.models import User, UserRole
from shop_backend.security.password import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create admin user")
    parser.add_argument("--username", type=str, default=None)
    parser.add_argument("--email", type=str, default=None)
    parser.add_argument("--password", type=str, default=None)
    args = parser.parse_args()

    print("=== Create Admin User ===\n")

    username = args.username or input("Username: ").strip()
    if not username:
        print("Error: username cannot be empty")
        sys.exit(1)

    email = args.email or input("Email: ").strip()
    if not email:
        print("Error: email cannot be empty")
        sys.exit(1)

    if args.password:
        password = args.password
    else:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Error: passwords do not match")
            sys.exit(1)

    if len(password) < 6:
        print("Error: password must be at least 6 characters")
        sys.exit(1)

    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            print(f"Error: username '{username}' already exists")
            sys.exit(1)
        if db.query(User).filter(User.email == email).first():
            print(f"Error: email '{email}' already exists")
            sys.exit(1)

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.admin,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"\nAdmin created successfully!")
        print(f"  ID:       {user.id}")
        print(f"  Username: {user.username}")
        print(f"  Email:    {user.email}")
        print(f"  Role:     {user.role.value}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
