"""Tutor Agent conversation log — this IS the Memory Agent's long-term store
(no separate memory table; other agents query this table directly rather than
through an intermediary cache)."""
import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class MessageRole(str, enum.Enum):
    user = "user"
    tutor = "tutor"


class TutorMessage(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "tutor_messages"

    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id"))
    submission_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("submissions.id"))
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, name="message_role"))
    content: Mapped[str] = mapped_column(Text)
