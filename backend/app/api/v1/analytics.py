"""
Analytics — Teacher/Admin dashboard endpoints. Every route is gated to the
owning teacher or an admin (see analytics_service.py's _ensure_course_access);
a different teacher, even if approved, gets a 403, matching the ownership
pattern established in assignments.py.

Uses plain require_role(teacher, admin) rather than require_approved_teacher
— that dependency only handles the teacher case, not the teacher-OR-admin
combination every route here needs. This is still safe: an unapproved
teacher can't own any course in the first place (course creation already
requires require_approved_teacher), so the ownership check below rejects
them the same way it would reject any other non-owning teacher.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.db.models.user import User, UserRole
from app.services import analytics_service
from app.services.analytics_service import NotFoundError, OwnershipError

router = APIRouter(tags=["analytics"])


def _http_error(e: Exception):
    if isinstance(e, NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, OwnershipError):
        return HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


async def _teacher_id_and_admin_flag(db: AsyncSession, user: User) -> tuple[uuid.UUID | None, bool]:
    if user.role == UserRole.admin:
        return None, True
    await db.refresh(user, attribute_names=["teacher"])
    if user.teacher is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="No teacher profile on this account.")
    return user.teacher.id, False


@router.post("/assignments/{assignment_id}/analytics/refresh")
async def refresh_assignment_analytics(
    assignment_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    teacher_id, is_admin = await _teacher_id_and_admin_flag(db, user)
    try:
        snapshot = await analytics_service.compute_assignment_analytics(db, assignment_id, teacher_id, is_admin)
    except (NotFoundError, OwnershipError) as e:
        raise _http_error(e)
    return {"generated_at": snapshot.generated_at, "metrics": snapshot.metrics}


@router.get("/assignments/{assignment_id}/analytics")
async def get_assignment_analytics(
    assignment_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    teacher_id, is_admin = await _teacher_id_and_admin_flag(db, user)
    try:
        snapshot = await analytics_service.get_latest_assignment_analytics(db, assignment_id, teacher_id, is_admin)
    except (NotFoundError, OwnershipError) as e:
        raise _http_error(e)
    return {"generated_at": snapshot.generated_at, "metrics": snapshot.metrics}


@router.post("/courses/{course_id}/analytics/refresh")
async def refresh_course_analytics(
    course_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    teacher_id, is_admin = await _teacher_id_and_admin_flag(db, user)
    try:
        snapshot = await analytics_service.compute_course_analytics(db, course_id, teacher_id, is_admin)
    except (NotFoundError, OwnershipError) as e:
        raise _http_error(e)
    return {"generated_at": snapshot.generated_at, "metrics": snapshot.metrics}


@router.get("/courses/{course_id}/analytics")
async def get_course_analytics(
    course_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    teacher_id, is_admin = await _teacher_id_and_admin_flag(db, user)
    try:
        snapshot = await analytics_service.get_latest_course_analytics(db, course_id, teacher_id, is_admin)
    except (NotFoundError, OwnershipError) as e:
        raise _http_error(e)
    return {"generated_at": snapshot.generated_at, "metrics": snapshot.metrics}
