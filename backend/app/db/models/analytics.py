"""Materialized analytics snapshots — the Analytics Agent writes here rather than
recomputing aggregates from raw submissions on every dashboard load."""
import uuid

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin


class AnalyticsSnapshot(UUIDPKMixin, Base):
    __tablename__ = "analytics_snapshots"

    scope: Mapped[str] = mapped_column(String(20))  # assignment|course
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    generated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
