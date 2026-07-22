"""initial schema — full Phase 0 schema (auth tables used starting Phase 1,
academic/assignment/submission/analytics/document/conversation tables used
starting their respective phases; all created now so later phases are pure
application code with no further structural migration debt).

Revision ID: 0001
Revises:
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE on a bug that used to live here: each ENUM below was previously
    # explicitly `.create(bind, checkfirst=True)`-ed *and then* reused as-is
    # inside `create_table_if_missing(...)` column definitions. That second usage
    # carries its own `create_type=True` (the default), and Postgres's ENUM
    # DDL emits its "before create" CREATE TYPE unconditionally in that path
    # (checkfirst is not consistently honored there across SQLAlchemy
    # versions) — so table creation re-issued `CREATE TYPE user_role ...`
    # for a type that already existed, raising
    # `DuplicateObject: type "user_role" already exists` on the very first
    # run of this migration, every time. `create_type=False` on the objects
    # used in columns fixes that: creation happens exactly once, via the
    # explicit checkfirst=True calls below.
    #
    # Every step below is also individually idempotent (checkfirst for
    # enums, has_table/has_index guards for tables/indexes), so that if a
    # migration ever fails partway through for an unrelated reason, simply
    # re-running `alembic upgrade head` picks up wherever it left off
    # instead of erroring on objects a previous partial run already created.
    bind = op.get_bind()
    _state = {"inspector": sa.inspect(bind)}

    def enum_type(name: str, *values: str) -> postgresql.ENUM:
        enum = postgresql.ENUM(*values, name=name, create_type=False)
        enum.create(bind, checkfirst=True)
        return enum

    user_role = enum_type("user_role", "student", "teacher", "admin")
    verification_status = enum_type("verification_status", "pending", "approved", "rejected")
    assignment_type = enum_type(
        "assignment_type", "programming", "sql", "theory", "mcq", "case_study", "design"
    )
    test_case_kind = enum_type("test_case_kind", "public", "hidden", "edge")
    message_role = enum_type("message_role", "user", "tutor")

    def create_table_if_missing(name, *args, **kwargs):
        if not _state["inspector"].has_table(name):
            op.create_table(name, *args, **kwargs)
            _state["inspector"] = sa.inspect(bind)  # refresh so later has_table() calls see it

    def create_index_if_missing(index_name, table_name, columns, **kwargs):
        existing = (
            {ix["name"] for ix in _state["inspector"].get_indexes(table_name)}
            if _state["inspector"].has_table(table_name) else set()
        )
        if index_name not in existing:
            op.create_index(index_name, table_name, columns, **kwargs)

    create_table_if_missing(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_verified", sa.Boolean, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
    )
    create_index_if_missing("ix_users_email", "users", ["email"])

    create_table_if_missing(
        "students",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), unique=True),
        sa.Column("student_number", sa.String(50)),
    )

    create_table_if_missing(
        "teachers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), unique=True),
        sa.Column("institution", sa.String(255)),
        sa.Column("verification_status", verification_status, server_default="pending"),
    )

    create_table_if_missing(
        "verification_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teachers.id")),
        sa.Column("submitted_email_domain", sa.String(255)),
        sa.Column("status", verification_status, server_default="pending"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )

    create_table_if_missing(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("refresh_token_hash", sa.String(255)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )

    create_table_if_missing(
        "subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
    )

    create_table_if_missing(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id")),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teachers.id")),
    )

    create_table_if_missing(
        "assignment_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("assignment_type", assignment_type),
        sa.Column("default_fields", postgresql.JSONB, server_default="{}"),
    )

    create_table_if_missing(
        "assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id")),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assignment_templates.id")),
        sa.Column("type", assignment_type),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("difficulty", sa.String(50)),
        sa.Column("constraints", postgresql.JSONB, server_default="{}"),
        sa.Column("timeout_seconds", sa.Integer, server_default="5"),
    )

    create_table_if_missing(
        "rubrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assignments.id"), unique=True),
        sa.Column("criteria", postgresql.JSONB, server_default="[]"),
    )

    create_table_if_missing(
        "test_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assignments.id")),
        sa.Column("kind", test_case_kind),
        sa.Column("input", postgresql.JSONB),
        sa.Column("expected_output", postgresql.JSONB),
        sa.Column("points", sa.Integer, server_default="1"),
    )

    create_table_if_missing(
        "submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assignments.id")),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id")),
        sa.Column("language", sa.String(50)),
        sa.Column("content", sa.Text),
    )

    create_table_if_missing(
        "execution_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("submissions.id"), unique=True),
        sa.Column("status", sa.String(30)),
        sa.Column("raw_output", postgresql.JSONB, server_default="{}"),
        sa.Column("runtime_ms", sa.Float),
    )

    create_table_if_missing(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("submissions.id"), unique=True),
        sa.Column("score", sa.Float, server_default="0"),
        sa.Column("total_points", sa.Float, server_default="0"),
        sa.Column("breakdown", postgresql.JSONB, server_default="[]"),
        sa.Column("strengths", sa.Text),
        sa.Column("weaknesses", sa.Text),
        sa.Column("hints", postgresql.JSONB, server_default="[]"),
    )

    create_table_if_missing(
        "similarity_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assignments.id")),
        sa.Column("submission_a_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("submissions.id")),
        sa.Column("submission_b_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("submissions.id")),
        sa.Column("technique", sa.String(30)),
        sa.Column("score", sa.Float),
    )

    create_table_if_missing(
        "analytics_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope", sa.String(20)),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True)),
        sa.Column("metrics", postgresql.JSONB, server_default="{}"),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    create_table_if_missing(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id")),
        sa.Column("filename", sa.String(255)),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("teachers.id")),
    )

    create_table_if_missing(
        "tutor_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id")),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("submissions.id")),
        sa.Column("role", message_role),
        sa.Column("content", sa.Text),
    )


def downgrade() -> None:
    for table in (
        "tutor_messages", "documents", "analytics_snapshots", "similarity_reports",
        "feedback", "execution_results", "submissions", "test_cases", "rubrics",
        "assignments", "assignment_templates", "courses", "subjects", "sessions",
        "verification_requests", "teachers", "students", "users",
    ):
        op.drop_table(table)

    bind = op.get_bind()
    for enum_name in ("message_role", "test_case_kind", "assignment_type", "verification_status", "user_role"):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)
