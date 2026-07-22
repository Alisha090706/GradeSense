"""Subjects (DSA, OS, CN, DBMS, OOP, SE, ...) and Courses."""
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class Subject(UUIDPKMixin, Base):
    __tablename__ = "subjects"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    courses: Mapped[list["Course"]] = relationship(back_populates="subject")


class Course(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "courses"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"))
    teacher_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("teachers.id"))

    subject: Mapped["Subject"] = relationship(back_populates="courses")
    teacher: Mapped["Teacher"] = relationship(back_populates="courses")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="course")
    documents: Mapped[list["Document"]] = relationship(back_populates="course")
