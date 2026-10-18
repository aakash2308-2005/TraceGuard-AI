"""Case management service with case isolation and audit logging."""

import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.rbac import CaseRole
from app.domain.errors import ConflictError, NotFoundError, ValidationError
from app.persistence.postgres.models import Case, CaseMembership, User
from app.services.audit_service import AuditService


class CaseService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._audit = AuditService(session)

    async def create_case(
        self,
        *,
        case_identifier: str = "",
        title: str,
        description: str | None,
        creator_id: uuid.UUID,
        case_role: str = CaseRole.LEAD.value,
    ) -> Case:
        """Create a case and add the creator with the selected case role."""
        if case_role not in {role.value for role in CaseRole}:
            raise ValidationError(f"Invalid case role: {case_role}")
        case = Case(
            case_identifier=case_identifier or str(uuid.uuid4()),
            title=title,
            description=description,
            created_by=creator_id,
        )
        self._session.add(case)
        await self._session.flush()

        membership = CaseMembership(
            case_id=case.id, user_id=creator_id, case_role=case_role
        )
        self._session.add(membership)
        await self._audit.record(
            "case.created", actor_id=creator_id, case_id=case.id, detail={"title": title}
        )
        await self._session.flush()
        return case

    async def list_cases_for_user(self, user_id: uuid.UUID, is_admin: bool) -> list[tuple[Case, str | None]]:
        """List cases the user can see. Admins see all; others see memberships.

        The role in each row is always *this user's* case role — admins see every
        case, but only cases they belong to carry a role (None renders as "—").
        """
        if is_admin:
            result = await self._session.execute(
                select(Case, CaseMembership.case_role)
                .outerjoin(
                    CaseMembership,
                    and_(
                        CaseMembership.case_id == Case.id,
                        CaseMembership.user_id == user_id,
                    ),
                )
            )
            return [(row[0], row[1]) for row in result.all()]

        result = await self._session.execute(
            select(Case, CaseMembership.case_role)
            .join(CaseMembership, CaseMembership.case_id == Case.id)
            .where(CaseMembership.user_id == user_id)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def update_case(
        self, case: Case, *, title: str | None, description: str | None, status: str | None,
        actor_id: uuid.UUID,
    ) -> Case:
        if title is not None:
            case.title = title
        if description is not None:
            case.description = description
        if status is not None:
            case.status = status
        await self._audit.record("case.updated", actor_id=actor_id, case_id=case.id)
        await self._session.flush()
        return case

    async def add_member(
        self, *, case_id: uuid.UUID, user_id: uuid.UUID, case_role: str, actor_id: uuid.UUID
    ) -> CaseMembership:
        valid_roles = {r.value for r in CaseRole}
        if case_role not in valid_roles:
            raise ValidationError(f"Invalid case role: {case_role}")
        user = await self._session.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        existing = await self._session.execute(
            select(CaseMembership).where(
                CaseMembership.case_id == case_id, CaseMembership.user_id == user_id
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("User already a member of this case")
        membership = CaseMembership(case_id=case_id, user_id=user_id, case_role=case_role)
        self._session.add(membership)
        await self._audit.record(
            "case.member_added", actor_id=actor_id, case_id=case_id,
            detail={"user_id": str(user_id), "case_role": case_role},
        )
        await self._session.flush()
        return membership

    async def list_members(self, case_id: uuid.UUID) -> list[tuple[CaseMembership, User]]:
        result = await self._session.execute(
            select(CaseMembership, User)
            .join(User, User.id == CaseMembership.user_id)
            .where(CaseMembership.case_id == case_id)
            .options(selectinload(CaseMembership.user))
        )
        return [(row[0], row[1]) for row in result.all()]

    async def remove_member(
        self, *, case_id: uuid.UUID, user_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None:
        result = await self._session.execute(
            select(CaseMembership).where(
                CaseMembership.case_id == case_id, CaseMembership.user_id == user_id
            )
        )
        membership = result.scalar_one_or_none()
        if membership is None:
            raise NotFoundError("Membership not found")
        await self._session.delete(membership)
        await self._audit.record(
            "case.member_removed", actor_id=actor_id, case_id=case_id,
            detail={"user_id": str(user_id)},
        )
        await self._session.flush()
