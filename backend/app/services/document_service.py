"""
Course document upload/list/delete — business logic behind
api/v1/documents.py, wrapping retrieval_agent.py's ingest pipeline with
DB persistence (the Document row) and ownership checks.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.retrieval_agent import IngestInput, RetrievalAgent
from app.agents import vector_store
from app.db.models.academic import Course
from app.db.models.document import Document

_retrieval = RetrievalAgent()


class NotFoundError(Exception):
    pass


class OwnershipError(Exception):
    pass


async def _ensure_owner(db: AsyncSession, course_id: uuid.UUID, teacher_id: uuid.UUID) -> Course:
    course = await db.get(Course, course_id)
    if course is None:
        raise NotFoundError("Course not found.")
    if course.teacher_id != teacher_id:
        raise OwnershipError("You do not own this course.")
    return course


async def upload_document(
    db: AsyncSession, course_id: uuid.UUID, teacher_id: uuid.UUID, filename: str, content: bytes,
):
    await _ensure_owner(db, course_id, teacher_id)

    document = Document(course_id=course_id, filename=filename, uploaded_by=teacher_id)
    db.add(document)
    await db.flush()  # get document.id before ingesting, since chunks are keyed by it

    # Extraction/chunking errors (bad file type, unreadable PDF) propagate straight
    # up — caller turns these into a 400. The Document row is rolled back with the
    # transaction in that case (no orphan row for content that was never ingested).
    result = _retrieval.run(IngestInput(
        course_id=str(course_id), document_id=str(document.id), filename=filename, content=content,
    ))

    await db.commit()
    await db.refresh(document)
    return document, result


async def list_documents(db: AsyncSession, course_id: uuid.UUID) -> list[Document]:
    result = await db.execute(select(Document).where(Document.course_id == course_id))
    return list(result.scalars().all())


async def delete_document(db: AsyncSession, document_id: uuid.UUID, teacher_id: uuid.UUID) -> None:
    document = await db.get(Document, document_id)
    if document is None:
        raise NotFoundError("Document not found.")
    await _ensure_owner(db, document.course_id, teacher_id)

    vector_store.delete_document(str(document.course_id), str(document.id))
    await db.delete(document)
    await db.commit()
