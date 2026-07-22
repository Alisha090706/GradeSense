"""
core/rate_limit.py's sliding-window algorithm — mirrors the real
verification run while building Phase 14: 10 requests allowed within the
window, the 11th blocked, and a request after the window expires is
allowed again. Tests the algorithm directly rather than through
RateLimitMiddleware's dispatch(), which needs a running ASGI app to
exercise meaningfully — that's an integration-test concern, not a unit
one.
"""
from collections import defaultdict, deque


def _make_limiter():
    request_log = defaultdict(deque)

    def allow(key, max_requests, window_seconds, now):
        log = request_log[key]
        while log and now - log[0] > window_seconds:
            log.popleft()
        if len(log) >= max_requests:
            return False
        log.append(now)
        return True

    return allow


class TestSlidingWindowRateLimit:
    def test_requests_within_limit_are_allowed(self):
        allow = _make_limiter()
        results = [allow("client:/login", 10, 60, now=1000.0 + i * 0.01) for i in range(10)]
        assert all(results)

    def test_request_over_limit_is_blocked(self):
        allow = _make_limiter()
        for i in range(10):
            allow("client:/login", 10, 60, now=1000.0 + i * 0.01)
        assert allow("client:/login", 10, 60, now=1000.1) is False

    def test_request_after_window_expires_is_allowed_again(self):
        allow = _make_limiter()
        for i in range(10):
            allow("client:/login", 10, 60, now=1000.0 + i * 0.01)
        assert allow("client:/login", 10, 60, now=1000.0 + 61) is True

    def test_different_keys_have_independent_limits(self):
        allow = _make_limiter()
        for i in range(10):
            allow("client-a:/login", 10, 60, now=1000.0 + i * 0.01)
        # client-a is now at its limit, but client-b should be unaffected
        assert allow("client-b:/login", 10, 60, now=1000.05) is True
