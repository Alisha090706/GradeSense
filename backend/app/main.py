"""
FastAPI application factory — Phase 14 (final phase on the roadmap).

Health checks, auth, the user's own profile, admin verification queue,
subjects/courses/assignments, test-case + rubric generation, real
submissions across four assignment types with multi-technique similarity
checking, Teacher/Admin analytics, course document ingestion, and the
Tutor Agent are all mounted, alongside the temporary agents-demo router.
Phase 14 adds the hardening pass: rate limiting on auth endpoints
(core/rate_limit.py), structured JSON request logging
(core/logging_config.py), and — the most valuable part — a real pytest
suite (see /tests) covering every pure-computation agent across every
phase. See ARCHITECTURE.md for the full roadmap this was built against.
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import 
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging_config import RequestLoggingMiddleware, configure_logging
from app.core.rate_limit import RateLimitMiddleware
from app.db.session import AsyncSessionLocal
from app.api.v1 import (
    admin, agents_demo, analytics, assignments, auth, courses, documents, health, subjects, submissions, tutor, users,
)

settings = get_settings()
configure_logging(level="DEBUG" if settings.DEBUG else "INFO")


async def _bootstrap() -> None:
    """Runs once at process startup. Two independent, both-idempotent steps:

    1. Seed reference data (Subjects + Assignment Templates) — previously a
       separate manual `python -m scripts.seed_reference_data` step that was
       trivial to forget, and the direct cause of "the subject dropdown is
       empty" on a fresh environment. Always runs, safe in production too
       (it's pure INSERT-if-missing, see scripts/seed_reference_data.py).

    2. In DEBUG mode, if DEFAULT_ADMIN_EMAIL/PASSWORD are configured and no
       user with that email exists yet, create it as an admin — same effect
       as manually running `python -m scripts.create_admin`, just automatic.
       Without an admin account there is no way to approve any teacher
       through the (intentionally admin-gated — see require_approved_teacher
       in core/deps.py) approval workflow, which made that workflow
       effectively untestable rather than merely "working as designed".
       No-ops if either setting is unset, so production deployments that
       don't set them get no behavior change here.
    """
    from scripts.seed_reference_data import main as seed_reference_data
    await seed_reference_data()

    if settings.DEBUG and settings.DEFAULT_ADMIN_EMAIL and settings.DEFAULT_ADMIN_PASSWORD:
        from app.core import security
        from app.db.models.user import User, UserRole

        async with AsyncSessionLocal() as db:
            existing = (
                await db.execute(select(User).where(User.email == settings.DEFAULT_ADMIN_EMAIL))
            ).scalar_one_or_none()
            if existing is None:
                db.add(User(
                    email=settings.DEFAULT_ADMIN_EMAIL,
                    hashed_password=security.hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                    role=UserRole.admin,
                    is_verified=True,
                    is_active=True,
                ))
                await db.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        await _bootstrap()
    except Exception:
        # Never let a bootstrap hiccup (e.g. DB not reachable yet at boot) crash the
        # whole app — the API should still come up so /docs and /health work, and the
        # existing manual scripts remain a fallback either way.
        logging.getLogger("gradesense").exception("Startup bootstrap failed; continuing without it")
    yield


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Order matters: middleware runs outside-in on the request, inside-out on the
# response — logging wraps rate limiting so a 429 still gets logged with a
# real duration and request ID, not silently dropped before logging sees it.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(subjects.router, prefix="/api/v1")
app.include_router(courses.router, prefix="/api/v1")
app.include_router(assignments.router, prefix="/api/v1")
app.include_router(submissions.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(tutor.router, prefix="/api/v1")
# Legacy/demo — superseded by the real DB-backed routes above. Left mounted for now
# since it's still handy for exercising the raw agent pipeline without DB setup.
app.include_router(agents_demo.router, prefix="/api/v1")


@app.get("/debug")
def debug():
    return {
        "frontend_origin": settings.FRONTEND_ORIGIN,
        "env": settings.ENV,
        "debug": settings.DEBUG,
    }


@app.get("/")
def root():
    return {"app": settings.APP_NAME, "env": settings.ENV, "docs": "/docs"}