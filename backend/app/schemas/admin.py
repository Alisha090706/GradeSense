"""Response/request models for the admin teacher-verification queue."""
import datetime as dt
import uuid

from pydantic import BaseModel

from app.db.models.user import VerificationStatus


class VerificationRequestOut(BaseModel):
    id: uuid.UUID
    teacher_id: uuid.UUID
    teacher_email: str
    institution: str | None
    submitted_email_domain: str
    likely_institutional: bool
    status: VerificationStatus
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class VerificationDecisionRequest(BaseModel):
    note: str | None = None
