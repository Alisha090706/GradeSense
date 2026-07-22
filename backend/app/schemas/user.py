"""Response models describing the authenticated user."""
import uuid

from pydantic import BaseModel

from app.db.models.user import UserRole, VerificationStatus


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole
    is_verified: bool
    is_active: bool

    model_config = {"from_attributes": True}


class MeOut(BaseModel):
    user: UserOut
    teacher_verification_status: VerificationStatus | None = None
