"""Request/response models for the auth API (api/v1/auth.py)."""
from pydantic import BaseModel, EmailStr, Field


class StudentRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    student_number: str | None = None


class TeacherRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    institution: str | None = None


class RegisterResponse(BaseModel):
    message: str
    # Simulates the email that would be sent — see auth_service.py docstring.
    # Never include this field in a real deployment's response; it exists so the
    # platform is testable/demoable without an SMTP provider configured.
    dev_verification_token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
