"""
Password hashing + JWT helpers.

Not wired into any route yet (that's Phase 1 — full auth), but defined now
alongside the rest of core/ since it's foundational infrastructure other
Phase-1 code will import directly, and there's no reason to invent it twice.
"""
import datetime as dt
import hashlib

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def create_token(subject: str, expires_delta: dt.timedelta, extra_claims: dict | None = None) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + expires_delta}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, role: str) -> str:
    return create_token(
        subject,
        dt.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims={"role": role, "type": "access"},
    )


def create_refresh_token(subject: str) -> str:
    return create_token(
        subject,
        dt.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        extra_claims={"type": "refresh"},
    )


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError (or a subclass) on an invalid/expired token — callers
    (get_current_user, the refresh/logout routes) are responsible for turning that
    into a 401."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def hash_refresh_token(raw_token: str) -> str:
    """Refresh tokens are looked up by exact match (in the refresh/logout routes), so
    they're hashed with plain SHA-256 rather than bcrypt — bcrypt's per-hash salt makes
    it correct for passwords (verify-only, never re-derive) but wrong here, since we
    need a stable digest of the *token itself* to index sessions.refresh_token_hash by."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_email_verification_token(subject: str) -> str:
    return create_token(
        subject,
        dt.timedelta(minutes=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES),
        extra_claims={"type": "email_verification"},
    )
