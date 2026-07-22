"""
Shared FastAPI dependencies: DB session, current-user resolution, and
role-based access control.

require_role(...) is what every protected route depends on, rather than
checking request.state or a raw JWT payload ad hoc — this is the single
place role-gating logic lives, per the architecture doc's auth design (§2.5).
"""
import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.db.models.user import User, UserRole, VerificationStatus
from app.db.session import get_db  # noqa: F401  (re-exported for a single import site)

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if credentials is None:
        raise unauthorized
    try:
        payload = security.decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise unauthorized
    if payload.get("type") != "access":
        raise unauthorized

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_role(*roles: UserRole):
    """Usage: Depends(require_role(UserRole.teacher, UserRole.admin))"""
    async def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions for this action.")
        return user
    return _dependency


async def require_approved_teacher(
    user: User = Depends(require_role(UserRole.teacher)),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Not used by any route yet (Phase 2's course/assignment-creation routes are the
    first consumers) — defined here now since it's pure auth-layer logic and belongs
    next to require_role, not scattered into Phase 2's own module."""
    await db.refresh(user, attribute_names=["teacher"])
    if user.teacher is None or user.teacher.verification_status != VerificationStatus.approved:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Your teacher account is not yet approved by an administrator.",
        )
    return user
