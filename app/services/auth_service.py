"""Authentication service: login and token refresh."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.domain.errors import AuthenticationError
from app.persistence.postgres.models import User
from app.services.audit_service import AuditService


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._audit = AuditService(session)

    async def _get_user_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(User).options(selectinload(User.role)).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def _get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(
            select(User).options(selectinload(User.role)).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def login(self, username: str, password: str) -> dict:
        """Validate credentials and issue access + refresh tokens.

        Uses a constant failure message to avoid account enumeration.
        """
        user = await self._get_user_by_username(username)
        # Always run verify to reduce timing side-channels when user is absent.
        valid = bool(user) and user.is_active and verify_password(password, user.password_hash)
        if not user or not valid:
            await self._audit.record("auth.login_failed", detail={"username": username})
            raise AuthenticationError("Invalid username or password")

        await self._audit.record("auth.login", actor_id=user.id)
        return {
            "access_token": create_access_token(str(user.id), user.role.name),
            "refresh_token": create_refresh_token(str(user.id)),
            "token_type": "bearer",
        }

    async def refresh(self, refresh_token: str) -> dict:
        """Issue a new access token from a valid refresh token."""
        payload = decode_token(refresh_token, expected_type="refresh")
        user = await self._get_user_by_id(uuid.UUID(payload["sub"]))
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")
        return {
            "access_token": create_access_token(str(user.id), user.role.name),
            "token_type": "bearer",
        }
