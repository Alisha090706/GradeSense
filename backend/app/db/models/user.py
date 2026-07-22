"""
Auth-related tables: users (single table, role-differentiated), the 1:1
student/teacher profile extensions, teacher verification requests, and
refresh-token sessions. Wired up fully in Phase 1 — defined now so the
rest of the schema (which FKs into users/students/teachers) has something
to point at.
"""
import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class UserRole(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"


class VerificationStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class User(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # email verified
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    student: Mapped["Student"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    teacher: Mapped["Teacher"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Student(UUIDPKMixin, Base):
    __tablename__ = "students"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    student_number: Mapped[str | None] = mapped_column(String(50))

    user: Mapped["User"] = relationship(back_populates="student")


class Teacher(UUIDPKMixin, Base):
    __tablename__ = "teachers"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    institution: Mapped[str | None] = mapped_column(String(255))
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status"), default=VerificationStatus.pending
    )

    user: Mapped["User"] = relationship(back_populates="teacher")
    courses: Mapped[list["Course"]] = relationship(back_populates="teacher")


class VerificationRequest(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "verification_requests"

    teacher_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("teachers.id"))
    submitted_email_domain: Mapped[str] = mapped_column(String(255))
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status"), default=VerificationStatus.pending
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))


class Session(UUIDPKMixin, TimestampMixin, Base):
    """Refresh-token sessions — one row per issued refresh token, so a token can be
    revoked (logout / logout-everywhere) by deleting its row rather than needing a
    server-side JWT blacklist for access tokens too."""
    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    refresh_token_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="sessions")
