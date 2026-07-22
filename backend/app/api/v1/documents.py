"""
Course document upload/list/delete — Phase 9 (Retrieval Agent). Every
mutating route requires the acting teacher to own the course, same
ownership pattern as assignments.py.

MAX_UPLOAD_SIZE_BYTES exists because document_extraction.py runs
in-process (no subprocess/timeout isolation the way LanguageRunners get) —
an unbounded upload is a real resource-exhaustion vector worth guarding
against explicitly rather than trusting client-side limits.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.document_extraction import ExtractionError, UnsupportedFormatError
from app.core.deps import get_current_user, get_db, require_approved_teacher
from app.db.models.user import User
from app.schemas.document import DocumentOut, DocumentUploadResult
from app.services import document_service
from app.services.document_service import NotFoundError, OwnershipError

router = APIRouter(tags=["documents"])

MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024  # 20MB


def _http_error(e: Exception):
    if isinstance(e, NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, OwnershipError):
        return HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/courses/{course_id}/documents", response_model=DocumentUploadResult, status_code=status.HTTP_201_CREATED)
async def upload_document(
    course_id: uuid.UUID, file: UploadFile, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_approved_teacher),
):
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                             detail=f"File exceeds the {MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB limit.")

    await db.refresh(teacher, attribute_names=["teacher"])
    try:
        document, result = await document_service.upload_document(
            db, course_id, teacher.teacher.id, file.filename, content,
        )
    except (NotFoundError, OwnershipError) as e:
        raise _http_error(e)
    except (UnsupportedFormatError, ExtractionError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))

    return DocumentUploadResult(
        document=DocumentOut.model_validate(document), chunk_count=result.chunk_count,
        indexed=result.indexed, note=result.note,
    )


@router.get("/courses/{course_id}/documents", response_model=list[DocumentOut])
async def list_documents(course_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    return await document_service.list_documents(db, course_id)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_approved_teacher),
):
    await db.refresh(teacher, attribute_names=["teacher"])
    try:
        await document_service.delete_document(db, document_id, teacher.teacher.id)
    except (NotFoundError, OwnershipError) as e:
        raise _http_error(e)
