"""
Tutor conversations — student-only (the Tutor talks to students about
their own work; teachers get analytics/feedback review instead, not a
chat interface with a student's submission).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.db.models.user import User, UserRole
from app.schemas.tutor import AskRequest, AskResponse, TutorMessageOut
from app.services import tutor_service
from app.services.tutor_service import NotFoundError, OwnershipError

router = APIRouter(prefix="/tutor", tags=["tutor"])


async def _student_id(db: AsyncSession, user: User) -> uuid.UUID:
    await db.refresh(user, attribute_names=["student"])
    if user.student is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="No student profile on this account.")
    return user.student.id


@router.post("/ask", response_model=AskResponse)
async def ask(
    payload: AskRequest, db: AsyncSession = Depends(get_db), user: User = Depends(require_role(UserRole.student)),
):
    student_id = await _student_id(db, user)
    try:
        result = await tutor_service.ask(db, student_id, payload.question, payload.submission_id)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    except OwnershipError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))
    return AskResponse(**result)


@router.get("/history", response_model=list[TutorMessageOut])
async def get_history(
    submission_id: uuid.UUID | None = Query(default=None), db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.student)),
):
    student_id = await _student_id(db, user)
    messages = await tutor_service.get_history(db, student_id, submission_id)
    return [TutorMessageOut(role=m.role.value, content=m.content, created_at=m.created_at) for m in messages]
