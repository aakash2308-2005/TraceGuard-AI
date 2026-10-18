"""Unit tests for password hashing and JWT tokens (no DB required)."""

import pytest

from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.domain.errors import AuthenticationError


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret-pass")
    assert hashed != "s3cret-pass"
    assert verify_password("s3cret-pass", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_contains_role():
    token = create_access_token("user-123", "admin")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "user-123"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_refresh_token_type_enforced():
    token = create_refresh_token("user-123")
    with pytest.raises(AuthenticationError):
        decode_token(token, expected_type="access")


def test_tampered_token_rejected():
    token = create_access_token("user-123", "investigator")
    with pytest.raises(AuthenticationError):
        decode_token(token + "tampered", expected_type="access")
