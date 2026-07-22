"""Course documents uploaded for RAG (Retrieval Agent, wired up in Phase 9).
This table is the source-of-truth metadata row; the actual chunk vectors live
in ChromaDB, keyed by this row's id in each chunk's metadata."""
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class Document(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id"))
    filename: Mapped[str] = mapped_column(String(255))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("teachers.id"))

    course: Mapped["Course"] = relationship(back_populates="documents")
