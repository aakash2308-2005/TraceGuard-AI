"""Unit tests for evidence tools: hashing, validation, indicator normalization."""

import hashlib
import io
import zipfile

import pytest

from app.domain.errors import ValidationError
from app.domain.indicators import normalize_indicator
from app.tools.file_validation import validate_file
from app.tools.hasher import sha256_bytes, sha256_stream


# --- Hasher ---
def test_sha256_bytes_matches_hashlib():
    data = b"evidence-bytes"
    assert sha256_bytes(data) == hashlib.sha256(data).hexdigest()


def test_sha256_stream_matches_bytes():
    chunks = [b"abc", b"def", b"ghi"]
    assert sha256_stream(chunks) == sha256_bytes(b"abcdefghi")


# --- File validation ---
_PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
_JPEG = b"\xff\xd8\xff" + b"0" * 32


def test_valid_png_passes():
    result = validate_file(data=_PNG, declared_mime="image/png", filename="a.png")
    assert result.mime_type == "image/png"
    assert result.sniffed_ok


def test_mime_mismatch_rejected():
    # PNG bytes declared as JPEG -> magic check fails.
    with pytest.raises(ValidationError):
        validate_file(data=_PNG, declared_mime="image/jpeg", filename="a.jpg")


def test_unsupported_mime_rejected():
    with pytest.raises(ValidationError):
        validate_file(data=_JPEG, declared_mime="application/x-msdownload", filename="x.exe")


def test_empty_file_rejected():
    with pytest.raises(ValidationError):
        validate_file(data=b"", declared_mime="image/png", filename="a.png")


def test_text_plain_accepts_text():
    result = validate_file(data=b"hello world\n", declared_mime="text/plain", filename="a.txt")
    assert result.mime_type == "text/plain"


def test_text_plain_rejects_binary():
    with pytest.raises(ValidationError):
        validate_file(data=b"\x00\x01\x02", declared_mime="text/plain", filename="a.txt")


def _make_zip_bomb_like() -> bytes:
    """A zip whose uncompressed/compressed ratio is very high."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("big.txt", b"0" * (2 * 1024 * 1024))  # highly compressible
    return buf.getvalue()


def test_zip_bomb_ratio_rejected():
    data = _make_zip_bomb_like()
    with pytest.raises(ValidationError):
        validate_file(data=data, declared_mime="application/zip", filename="b.zip")


def test_malformed_zip_rejected():
    # Valid zip magic prefix but corrupt body.
    data = b"PK\x03\x04" + b"garbage" * 10
    with pytest.raises(ValidationError):
        validate_file(data=data, declared_mime="application/zip", filename="b.zip")


# --- Indicator normalization ---
def test_normalize_email_lowercases():
    assert normalize_indicator("email", "  User@Example.COM ") == "user@example.com"


def test_normalize_domain_strips_trailing_dot():
    assert normalize_indicator("domain", "Example.COM.") == "example.com"


def test_normalize_ip_valid_and_invalid():
    assert normalize_indicator("ip", "192.168.000.001") == "192.168.0.1"
    with pytest.raises(ValidationError):
        normalize_indicator("ip", "999.1.1.1")


def test_normalize_wallet_and_tx():
    addr = "0x" + "A" * 40
    assert normalize_indicator("wallet", addr) == addr.lower()
    tx = "0x" + "B" * 64
    assert normalize_indicator("tx_hash", tx) == tx.lower()
    with pytest.raises(ValidationError):
        normalize_indicator("wallet", "0x123")


def test_normalize_rejects_unknown_type():
    with pytest.raises(ValidationError):
        normalize_indicator("passport", "123")
