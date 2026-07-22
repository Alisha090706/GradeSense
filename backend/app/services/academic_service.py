"""Subjects and Courses — business logic behind api/v1/subjects.py and courses.py."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.academic import Course, Subject


class NotFoundError(Exception):
    pass


async def create_subject(db: AsyncSession, name: str) -> Subject:
    subject = Subject(name=name)
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return subject


async def list_subjects(db: AsyncSession) -> list[Subject]:
    result = await db.execute(select(Subject).order_by(Subject.name))
    return list(result.scalars().all())


async def create_course(db: AsyncSession, teacher_id: uuid.UUID, name: str, subject_id: uuid.UUID) -> Course:
    if await db.get(Subject, subject_id) is None:
        raise NotFoundError("Subject not found.")
    course = Course(name=name, subject_id=subject_id, teacher_id=teacher_id)
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


async def list_courses(db: AsyncSession, teacher_id: uuid.UUID | None = None) -> list[Course]:
    stmt = select(Course)
    if teacher_id is not None:
        stmt = stmt.where(Course.teacher_id == teacher_id)
    result = await db.execute(stmt.order_by(Course.name))
    return list(result.scalars().all())


async def get_course(db: AsyncSession, course_id: uuid.UUID) -> Course:
    course = await db.get(Course, course_id)
    if course is None:
        raise NotFoundError("Course not found.")
    return course
