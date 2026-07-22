"""
core/security.py — mirrors the real JWT lifecycle simulation from Phase 1:
access/refresh/email-verification tokens round-trip correctly with the
right "type" claim, an expired token is correctly rejected, and the
refresh-token hash is deterministic (required for session lookup by hash
in auth_service.py — a non-deterministic hash would make every refresh
attempt fail to find its own session row).

Testing note: the JWT and hashing tests below (TestTokenLifecycle,
TestRefreshTokenHash) were verified for real while building this — this
sandbox has PyJWT installed. TestPasswordHashing was not — passlib isn't
installed here, so those three assertions are code-reviewed against
passlib's documented behavior, not run. Flagged rather than left to look
uniformly verified when it isn't.
"""
import datetime as dt

import jwt
import pytest

from app.core import security


class TestTokenLifecycle:
    def test_access_token_has_correct_claims(self):
        token = security.create_access_token("user-123", role="student")
        payload = security.decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "student"
        assert payload["type"] == "access"

    def test_refresh_token_has_correct_type(self):
        token = security.create_refresh_token("user-123")
        payload = security.decode_token(token)
        assert payload["type"] == "refresh"

    def test_email_verification_token_has_correct_type(self):
        token = security.create_email_verification_token("user-123")
        payload = security.decode_token(token)
        assert payload["type"] == "email_verification"

    def test_expired_token_is_rejected(self):
        expired = security.create_token("user-123", dt.timedelta(seconds=-1), {"type": "access"})
        with pytest.raises(jwt.ExpiredSignatureError):
            security.decode_token(expired)

    def test_tampered_token_is_rejected(self):
        token = security.create_access_token("user-123", role="student")
        tampered = token[:-4] + "abcd"
        with pytest.raises(jwt.PyJWTError):
            security.decode_token(tampered)


class TestRefreshTokenHash:
    def test_hash_is_deterministic(self):
        token = security.create_refresh_token("user-123")
        assert security.hash_refresh_token(token) == security.hash_refresh_token(token)

    def test_different_tokens_hash_differently(self):
        t1 = security.create_refresh_token("user-123")
        t2 = security.create_refresh_token("user-456")
        assert security.hash_refresh_token(t1) != security.hash_refresh_token(t2)


class TestPasswordHashing:
    def test_correct_password_verifies(self):
        hashed = security.hash_password("correct horse battery staple")
        assert security.verify_password("correct horse battery staple", hashed) is True

    def test_wrong_password_does_not_verify(self):
        hashed = security.hash_password("correct horse battery staple")
        assert security.verify_password("wrong password", hashed) is False

    def test_hash_is_not_the_plaintext(self):
        hashed = security.hash_password("correct horse battery staple")
        assert hashed != "correct horse battery staple"
