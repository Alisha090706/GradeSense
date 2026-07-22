"""
Admin routes: the teacher-verification queue. Every route here requires
role=admin via require_role — see core/deps.py.
"""
import uuid
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.db.models.user import (
    Teacher, User, UserRole, VerificationRequest, VerificationStatus,
)
from app.schemas.admin import VerificationDecisionRequest, VerificationRequestOut
from app.services.auth_service import is_institutional_domain

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_role(UserRole.admin))],
)


async def _to_out(db: AsyncSession, vr: VerificationRequest) -> VerificationRequestOut:
    teacher = await db.get(Teacher, vr.teacher_id)
    user = await db.get(User, teacher.user_id)
    return VerificationRequestOut(
        id=vr.id,
        teacher_id=vr.teacher_id,
        teacher_email=user.email,
        institution=teacher.institution,
        submitted_email_domain=vr.submitted_email_domain,
        likely_institutional=is_institutional_domain(user.email),
        status=vr.status,
        created_at=vr.created_at,
    )


@router.get("/verification-requests", response_model=list[VerificationRequestOut])
async def list_verification_requests(
    status_filter: VerificationStatus = VerificationStatus.pending,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(VerificationRequest).where(VerificationRequest.status == status_filter))
    return [await _to_out(db, vr) for vr in result.scalars().all()]


async def _decide(
    request_id: uuid.UUID, decision: VerificationStatus, db: AsyncSession, admin: User,
) -> VerificationRequestOut:
    vr = await db.get(VerificationRequest, request_id)
    if vr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Verification request not found.")

    teacher = await db.get(Teacher, vr.teacher_id)
    vr.status = decision
    vr.reviewed_by = admin.id
    vr.reviewed_at = dt.datetime.now(dt.timezone.utc)
    teacher.verification_status = decision
    await db.commit()
    await db.refresh(vr)
    return await _to_out(db, vr)


@router.post("/verification-requests/{request_id}/approve", response_model=VerificationRequestOut)
async def approve_verification_request(
    request_id: uuid.UUID,
    _payload: VerificationDecisionRequest = VerificationDecisionRequest(),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.admin)),
):
    return await _decide(request_id, VerificationStatus.approved, db, admin)


@router.post("/verification-requests/{request_id}/reject", response_model=VerificationRequestOut)
async def reject_verification_request(
    request_id: uuid.UUID,
    _payload: VerificationDecisionRequest = VerificationDecisionRequest(),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.admin)),
):
    return await _decide(request_id, VerificationStatus.rejected, db, admin)
