"""Response models for course document upload/list."""
import datetime as dt
import uuid

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    filename: str
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class DocumentUploadResult(BaseModel):
    document: DocumentOut
    chunk_count: int
    indexed: bool
    note: str
