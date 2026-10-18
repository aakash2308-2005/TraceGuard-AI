"""Shared pytest fixtures."""

import os

import pytest

# Force mock modes so tests never touch real external services.
os.environ.setdefault("LLM_MODE", "mock")
os.environ.setdefault("OSINT_MODE", "mock")
os.environ.setdefault("CRYPTO_MODE", "mock")
os.environ.setdefault("IBMZ_MODE", "mock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-key")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
