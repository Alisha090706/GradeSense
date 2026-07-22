"""Courses — created by approved teachers, listable by anyone authenticated."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_approved_teacher
from app.db.models.user import User
from app.schemas.academic import CourseCreate, CourseOut
from app.services import academic_service
from app.services.academic_service import NotFoundError

router = APIRouter(prefix="/courses", tags=["courses"])


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CourseCreate, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_approved_teacher),
):
    await db.refresh(teacher, attribute_names=["teacher"])
    try:
        return await academic_service.create_course(db, teacher.teacher.id, payload.name, payload.subject_id)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("", response_model=list[CourseOut])
async def list_courses(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    return await academic_service.list_courses(db)


@router.get("/{course_id}", response_model=CourseOut)
async def get_course(course_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        return await academic_service.get_course(db, course_id)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
