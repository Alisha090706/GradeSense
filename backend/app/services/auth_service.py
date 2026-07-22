"""
Auth business logic — registration, login, token issuance/refresh/revocation,
email verification. Routes in api/v1/auth.py stay thin wrappers around this.

Email verification note: there's no SMTP integration in this phase. In a real
deployment, register_student/register_teacher would hand the verification
token to an email-sending service instead of returning it to the caller.
For local development, the route returns it directly (as
`dev_verification_token`) so the flow is testable end-to-end with nothing
more than curl — this is called out explicitly in the API response schema's
docstring so it's never mistaken for production behavior.
"""
import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.db.models.user import (
    Session as SessionModel, Student, Teacher, User, UserRole, VerificationRequest, VerificationStatus,
)

settings = get_settings()


class AuthError(Exception):
    """Raised for any auth failure that should become a 4xx at the route layer.
    Routes catch this and set the appropriate status code — this module never
    imports FastAPI, so it stays testable without spinning up the app."""


def is_institutional_domain(email: str) -> bool:
    domain = email.rsplit("@", 1)[-1].lower()
    return any(domain.endswith(suffix) for suffix in settings.INSTITUTIONAL_EMAIL_SUFFIXES)


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def register_student(db: AsyncSession, email: str, password: str, student_number: str | None) -> tuple[User, str]:
    if await _get_user_by_email(db, email):
        raise AuthError("An account with this email already exists.")

    user = User(email=email, hashed_password=security.hash_password(password), role=UserRole.student)
    db.add(user)
    await db.flush()  # populate user.id without committing yet

    db.add(Student(user_id=user.id, student_number=student_number))
    await db.commit()
    await db.refresh(user)

    token = security.create_email_verification_token(str(user.id))
    return user, token


async def register_teacher(db: AsyncSession, email: str, password: str, institution: str | None) -> tuple[User, str]:
    if await _get_user_by_email(db, email):
        raise AuthError("An account with this email already exists.")

    user = User(email=email, hashed_password=security.hash_password(password), role=UserRole.teacher)
    db.add(user)
    await db.flush()

    teacher = Teacher(user_id=user.id, institution=institution, verification_status=VerificationStatus.pending)
    db.add(teacher)
    await db.flush()

    domain = email.rsplit("@", 1)[-1].lower()
    db.add(VerificationRequest(
        teacher_id=teacher.id,
        submitted_email_domain=domain,
        status=VerificationStatus.pending,
    ))
    await db.commit()
    await db.refresh(user)

    token = security.create_email_verification_token(str(user.id))
    return user, token


async def verify_email(db: AsyncSession, token: str) -> User:
    try:
        payload = security.decode_token(token)
    except Exception:
        raise AuthError("Invalid or expired verification link.")
    if payload.get("type") != "email_verification":
        raise AuthError("Invalid verification token.")

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None:
        raise AuthError("Account no longer exists.")

    user.is_verified = True
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    user = await _get_user_by_email(db, email)
    if user is None or not security.verify_password(password, user.hashed_password):
        # Same error for "no such user" and "wrong password" — don't leak which one.
        raise AuthError("Incorrect email or password.")
    if not user.is_active:
        raise AuthError("This account has been deactivated.")
    if not user.is_verified:
        raise AuthError("Please verify your email before logging in.")
    return user


async def issue_tokens(db: AsyncSession, user: User) -> tuple[str, str]:
    access_token = security.create_access_token(str(user.id), role=user.role.value)
    refresh_token = security.create_refresh_token(str(user.id))

    db.add(SessionModel(
        user_id=user.id,
        refresh_token_hash=security.hash_refresh_token(refresh_token),
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    await db.commit()
    return access_token, refresh_token


async def _get_session_for_token(db: AsyncSession, refresh_token: str) -> SessionModel | None:
    token_hash = security.hash_refresh_token(refresh_token)
    result = await db.execute(select(SessionModel).where(SessionModel.refresh_token_hash == token_hash))
    return result.scalar_one_or_none()


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> tuple[str, str]:
    """Validates the refresh token's signature/expiry AND that its session row still
    exists and hasn't expired server-side (so a logout / admin-revoke actually takes
    effect immediately, not just at JWT expiry), then rotates it — the old session row
    is deleted and a new one issued, so a stolen refresh token can't be replayed
    indefinitely after the legitimate client rotates past it."""
    try:
        payload = security.decode_token(refresh_token)
    except Exception:
        raise AuthError("Invalid or expired refresh token.")
    if payload.get("type") != "refresh":
        raise AuthError("Invalid refresh token.")

    session_row = await _get_session_for_token(db, refresh_token)
    if session_row is None:
        raise AuthError("Session has been revoked. Please log in again.")
    if session_row.expires_at < dt.datetime.now(dt.timezone.utc):
        await db.delete(session_row)
        await db.commit()
        raise AuthError("Session expired. Please log in again.")

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthError("Account no longer available.")

    await db.delete(session_row)
    await db.commit()
    return await issue_tokens(db, user)


async def revoke_session(db: AsyncSession, refresh_token: str) -> None:
    session_row = await _get_session_for_token(db, refresh_token)
    if session_row is not None:
        await db.delete(session_row)
        await db.commit()
