"""
Auth routes: registration (student/teacher), email verification, login,
token refresh, logout. All business logic lives in services/auth_service.py
— routes here only translate between HTTP and that layer.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.auth import (
    LoginRequest, RefreshRequest, RegisterResponse, StudentRegisterRequest,
    TeacherRegisterRequest, TokenResponse,
)
from app.services import auth_service
from app.services.auth_service import AuthError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register/student", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_student(payload: StudentRegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        _user, token = await auth_service.register_student(
            db, payload.email, payload.password, payload.student_number,
        )
    except AuthError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
    return RegisterResponse(
        message="Account created. Verify your email to log in.",
        dev_verification_token=token,
    )


@router.post("/register/teacher", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_teacher(payload: TeacherRegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        _user, token = await auth_service.register_teacher(
            db, payload.email, payload.password, payload.institution,
        )
    except AuthError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
    return RegisterResponse(
        message=(
            "Account created. Verify your email, then wait for an administrator to "
            "approve your teacher account before you can create courses."
        ),
        dev_verification_token=token,
    )


@router.post("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    try:
        user = await auth_service.verify_email(db, token)
    except AuthError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"message": "Email verified.", "email": user.email}


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await auth_service.authenticate(db, payload.email, payload.password)
    except AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(e))
    access_token, refresh_token = await auth_service.issue_tokens(db, user)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        access_token, refresh_token = await auth_service.refresh_tokens(db, payload.refresh_token)
    except AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.revoke_session(db, payload.refresh_token)
