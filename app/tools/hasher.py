"""SHA-256 integrity hashing (FR-007, FR-020)."""

import hashlib


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_stream(chunks) -> str:
    """Return SHA-256 over an iterable of byte chunks (memory-friendly)."""
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk)
    return digest.hexdigest()
