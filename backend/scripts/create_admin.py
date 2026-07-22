"""
One-off CLI to create the first admin account.

There is deliberately no API route for this — an "admin" role isn't
something any endpoint should be able to grant, even to another admin's
request, without a human running this script with direct DB/server access.
Every admin after the first can just be promoted the same way, or (in a
later phase) via a proper internal admin-management route restricted to
existing admins.

Usage:
    cd backend
    python -m scripts.create_admin admin@example.com
    (you'll be prompted for a password)
"""
import asyncio
import getpass
import sys

from sqlalchemy import select

from app.core import security
from app.db.models.user import User, UserRole
from app.db.session import AsyncSessionLocal


async def main(email: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            print(f"A user with email {email} already exists (role={existing.role.value}).")
            return

        user = User(
            email=email,
            hashed_password=security.hash_password(password),
            role=UserRole.admin,
            is_verified=True,   # admins skip the email-verification step
            is_active=True,
        )
        db.add(user)
        await db.commit()
        print(f"Admin account created: {email}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.create_admin <email>")
        sys.exit(1)
    email_arg = sys.argv[1]
    password_arg = getpass.getpass("Password: ")
    asyncio.run(main(email_arg, password_arg))
