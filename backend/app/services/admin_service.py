"""Admin service: user management and role bootstrap."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.rbac import ROLE_PERMISSIONS, GlobalRole
from app.auth.security import hash_password
from app.domain.errors import ConflictError, NotFoundError, ValidationError
from app.persistence.postgres.models import Role, User
from app.services.audit_service import AuditService


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._audit = AuditService(session)

    async def ensure_roles(self) -> dict[str, Role]:
        """Idempotently create the global roles. Returns name -> Role."""
        result = await self._session.execute(select(Role))
        existing = {r.name: r for r in result.scalars().all()}
        for role_name, perms in ROLE_PERMISSIONS.items():
            if role_name not in existing:
                role = Role(name=role_name, permissions=perms)
                self._session.add(role)
                existing[role_name] = role
        await self._session.flush()
        return existing

    async def _get_role(self, name: str) -> Role:
        result = await self._session.execute(select(Role).where(Role.name == name))
        role = result.scalar_one_or_none()
        if role is None:
            raise NotFoundError(f"Role not found: {name}")
        return role

    async def create_user(
        self,
        *,
        username: str,
        email: str,
        password: str,
        role: str,
        actor_id: uuid.UUID | None = None,
    ) -> User:
        valid_roles = {r.value for r in GlobalRole}
        if role not in valid_roles:
            raise ValidationError(f"Invalid role: {role}")
        existing = await self._session.execute(
            select(User).where((User.username == username) | (User.email == email))
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("Username or email already exists")
        role_obj = await self._get_role(role)
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role_id=role_obj.id,
        )
        self._session.add(user)
        await self._session.flush()
        await self._audit.record(
            "admin.user_created", actor_id=actor_id, detail={"username": username, "role": role}
        )
        return user

    async def list_users(self) -> list[User]:
        result = await self._session.execute(select(User).options(selectinload(User.role)))
        return list(result.scalars().all())
