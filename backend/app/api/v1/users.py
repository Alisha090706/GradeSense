"""The authenticated user's own profile."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.db.models.user import User, UserRole
from app.schemas.user import MeOut, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=MeOut)
async def read_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    teacher_status = None
    if user.role == UserRole.teacher:
        await db.refresh(user, attribute_names=["teacher"])
        teacher_status = user.teacher.verification_status if user.teacher else None
    return MeOut(user=UserOut.model_validate(user), teacher_verification_status=teacher_status)
