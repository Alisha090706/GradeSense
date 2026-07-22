"""Subjects (DSA, OS, CN, DBMS, OOP, SE, ...). Listing is open to any
authenticated user; creating a new subject is admin-only — subjects are a
shared, platform-wide taxonomy, not something individual teachers manage."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_role
from app.db.models.user import UserRole
from app.schemas.academic import SubjectCreate, SubjectOut
from app.services import academic_service

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("", response_model=list[SubjectOut])
async def list_subjects(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    return await academic_service.list_subjects(db)


@router.post(
    "", response_model=SubjectOut, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def create_subject(payload: SubjectCreate, db: AsyncSession = Depends(get_db)):
    return await academic_service.create_subject(db, payload.name)
