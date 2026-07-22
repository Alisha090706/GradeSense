"""
Rate limiting — Phase 14.

A simple in-memory sliding-window limiter, applied via middleware to
auth endpoints (login, register, refresh) where brute-forcing or account-
enumeration matters most. Deliberately NOT a general-purpose rate limiter
for every route — most of this API is already behind JWT auth, where the
bigger concern is a single compromised/malicious token hammering the
service, not anonymous brute force; that's a different problem
(per-user quota, not per-IP) and out of scope here.

Known, real limitation: this is in-process memory, not Redis-backed —
it resets on restart and does NOT share state across multiple worker
processes (`uvicorn --workers N` with N>1 gives each worker its own
independent limit, meaning the effective limit is N times higher than
configured). Fine for the single-process local-dev setup this whole
project targets; a real multi-worker deployment needs a shared store
(Redis, which the architecture doc already flags as the natural upgrade
path for background jobs — the same dependency would serve both).
"""
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# path prefix -> (max requests, window seconds)
RATE_LIMITED_PATHS = {
    "/api/v1/auth/login": (10, 60),
    "/api/v1/auth/register/student": (5, 60),
    "/api/v1/auth/register/teacher": (5, 60),
    "/api/v1/auth/refresh": (20, 60),
}

_request_log: dict[str, deque] = defaultdict(deque)


def _client_key(request: Request, path: str) -> str:
    # request.client.host is what's available without trusting a spoofable
    # X-Forwarded-For header by default — fine for direct-to-uvicorn local
    # dev; a real deployment behind a reverse proxy needs to configure
    # trusted proxy headers explicitly rather than blindly trusting them.
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:{path}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        limit_config = RATE_LIMITED_PATHS.get(path)
        if limit_config is None:
            return await call_next(request)

        max_requests, window_seconds = limit_config
        key = _client_key(request, path)
        now = time.monotonic()
        log = _request_log[key]

        while log and now - log[0] > window_seconds:
            log.popleft()

        if len(log) >= max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": f"Too many requests to {path} — try again in a bit."},
            )

        log.append(now)
        return await call_next(request)
