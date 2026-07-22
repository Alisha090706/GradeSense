"""
SQLAlchemy 2.0 declarative base + shared mixins.

Every model in db/models/ inherits from Base. Alembic's env.py imports
Base.metadata (via db.models, which imports every model so they're all
registered) to autogenerate/verify migrations against.
"""
import datetime as dt
import uuid

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDPKMixin:
    """Every table uses a UUID primary key rather than a serial int — avoids leaking
    row counts/creation order through the API and makes IDs safe to generate client-side
    if a future offline-first client ever needs that."""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
