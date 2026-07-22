"""
Central application settings, loaded from environment variables / a .env file.

Every other module reads configuration through this Settings object rather than
calling os.environ directly, so there is exactly one place that knows how the
app is configured (and exactly one place to change when a new setting is added).
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "GradeSense"
    ENV: str = "development"
    DEBUG: bool = True

    # --- Database ---
    # Async driver (asyncpg) for the running app; a sync driver (psycopg2) is used
    # separately by Alembic migrations, since Alembic's migration runner is sync.
    DATABASE_URL: str = "postgresql+asyncpg://gradesense:gradesense@localhost:5432/gradesense"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://gradesense:gradesense@localhost:5432/gradesense"

    # --- Auth (wired up in Phase 1, defined here now so config has one home) ---
    JWT_SECRET_KEY: str = "change-me-in-.env-before-any-real-deployment"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # Domain suffixes that get auto-flagged as "likely legitimate" on teacher signup.
    # Per the architecture doc: this only affects a label shown to the admin reviewer —
    # it never skips admin approval itself, since a domain suffix is trivially spoofable
    # in a self-reported email and shouldn't be trusted as sole verification.
    INSTITUTIONAL_EMAIL_SUFFIXES: list[str] = [".edu", ".ac.in", ".ac.uk", ".edu.au"]

    # --- LLM (provider-agnostic; see agents/llm_client.py) ---
    GEMINI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None  # kept for continuity with the original prototype

    # --- Vector store / embeddings (wired up starting Phase 9) ---
    CHROMA_PERSIST_DIR: str = "./vector_store"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # --- CORS ---
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # --- Dev/test bootstrap (see main.py's startup hook) ---
    # There is deliberately no API route that grants the admin role (see
    # scripts/create_admin.py's docstring) — that stays true here too. This
    # only lets *this* server process create the very first admin account
    # for itself at boot, in DEBUG mode, using credentials that must be
    # explicitly configured (no hardcoded default password). It exists
    # because "teacher accounts can't do anything until an admin approves
    # them, but there's no admin account and no way to get one without
    # separately running a CLI script with server/DB access" was, in
    # practice, indistinguishable from teacher approval being broken.
    # Leave unset in production — the startup hook no-ops without both
    # values set.
    DEFAULT_ADMIN_EMAIL: str | None = None
    DEFAULT_ADMIN_PASSWORD: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Cached so Settings() is only ever parsed once per process."""
    return Settings()
