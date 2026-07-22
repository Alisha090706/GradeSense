"""Request/response models for subjects and courses."""
import uuid

from pydantic import BaseModel, Field


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class SubjectOut(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    subject_id: uuid.UUID


class CourseOut(BaseModel):
    id: uuid.UUID
    name: str
    subject_id: uuid.UUID
    teacher_id: uuid.UUID

    model_config = {"from_attributes": True}
