"""
Importing this package registers every model on Base.metadata — Alembic's
env.py imports `app.db.models` (not individual model files) for exactly
this side effect, so every new model file added here is picked up
automatically without editing env.py again.
"""
from app.db.models.user import User, Student, Teacher, VerificationRequest, Session  # noqa: F401
from app.db.models.academic import Subject, Course  # noqa: F401
from app.db.models.assignment import AssignmentTemplate, Assignment, Rubric, TestCase  # noqa: F401
from app.db.models.submission import (  # noqa: F401
    Submission, ExecutionResult, Feedback, SimilarityReport,
)
from app.db.models.analytics import AnalyticsSnapshot  # noqa: F401
from app.db.models.document import Document  # noqa: F401
from app.db.models.conversation import TutorMessage  # noqa: F401
