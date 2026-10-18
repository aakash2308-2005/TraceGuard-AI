"""FastAPI dependencies: DB session, current user, RBAC, and case membership."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.rbac import CaseRole, role_can
from app.auth.security import decode_token
from app.domain.errors import AuthenticationError, AuthorizationError, NotFoundError
from app.persistence.postgres.database import get_db_session
from app.persistence.postgres.models import Case, CaseMembership, User

_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: uuid.UUID
    username: str
    email: str
    name: str | None
    role: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_db_session),
) -> CurrentUser:
    """Resolve the authenticated user from the bearer token."""
    if credentials is None:
        raise AuthenticationError("Missing bearer token")
    payload = decode_token(credentials.credentials, expected_type="access")
    user_id = uuid.UUID(payload["sub"])
    result = await session.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    return CurrentUser(
        id=user.id,
        username=user.username,
        email=user.email,
        name=user.full_name,
        role=user.role.name,
    )


def require_permission(permission: str) -> Callable:
    """Dependency factory enforcing a global-role permission."""

    async def _dep(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not role_can(current.role, permission):
            raise AuthorizationError(f"Missing permission: {permission}")
        return current

    return _dep


@dataclass
class CaseContext:
    user: CurrentUser
    case: Case
    case_role: str


async def _load_membership(
    session: AsyncSession, case_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Case, str]:
    case = await session.get(Case, case_id)
    if case is None:
        # Use 404 to avoid leaking case existence to non-members.
        raise NotFoundError("Case not found")
    result = await session.execute(
        select(CaseMembership).where(
            CaseMembership.case_id == case_id,
            CaseMembership.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise NotFoundError("Case not found")
    return case, membership.case_role


@dataclass
class RunContext:
    user: CurrentUser
    run_id: uuid.UUID
    case_id: uuid.UUID
    case_role: str


def require_run_access(write: bool = False) -> Callable:
    """Dependency factory for routes keyed by investigation_id.

    Resolves the run's case, then enforces case membership (admins bypass).
    """

    async def _dep(
        investigation_id: uuid.UUID,
        current: CurrentUser = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> RunContext:
        from app.persistence.postgres.models import InvestigationRun

        run = await session.get(InvestigationRun, investigation_id)
        if run is None:
            raise NotFoundError("Investigation not found")

        if current.role == "admin":
            return RunContext(
                user=current,
                run_id=investigation_id,
                case_id=run.case_id,
                case_role=CaseRole.LEAD.value,
            )

        _case, case_role = await _load_membership(session, run.case_id, current.id)
        from app.auth.rbac import CASE_WRITE_ROLES

        if write and CaseRole(case_role) not in CASE_WRITE_ROLES:
            raise AuthorizationError("Write access required on this case")
        return RunContext(
            user=current,
            run_id=investigation_id,
            case_id=run.case_id,
            case_role=case_role,
        )

    return _dep


@dataclass
class ReportContext:
    user: CurrentUser
    report_id: uuid.UUID
    case_id: uuid.UUID
    case_role: str


def require_report_access(approve: bool = False) -> Callable:
    """Dependency for routes keyed by report_id.

    Resolves the report's run -> case, enforces membership, and (optionally)
    approval capability. Admins bypass membership.
    """

    async def _dep(
        report_id: uuid.UUID,
        current: CurrentUser = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> ReportContext:
        from app.persistence.postgres.models import InvestigationRun, Report

        report = await session.get(Report, report_id)
        if report is None:
            raise NotFoundError("Report not found")
        run = await session.get(InvestigationRun, report.run_id)
        if run is None:
            raise NotFoundError("Report not found")

        if current.role == "admin":
            return ReportContext(
                user=current,
                report_id=report_id,
                case_id=run.case_id,
                case_role=CaseRole.LEAD.value,
            )

        _case, case_role = await _load_membership(session, run.case_id, current.id)
        from app.auth.rbac import CASE_APPROVE_ROLES

        if approve and CaseRole(case_role) not in CASE_APPROVE_ROLES:
            raise AuthorizationError("Approval access required on this case")
        return ReportContext(
            user=current,
            report_id=report_id,
            case_id=run.case_id,
            case_role=case_role,
        )

    return _dep


def require_case_member(write: bool = False, approve: bool = False) -> Callable:
    """Dependency factory enforcing case membership and optional capability.

    Admins bypass membership (they can act on any case) but their action is
    still audited by the calling service.
    """

    async def _dep(
        case_id: uuid.UUID,
        current: CurrentUser = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> CaseContext:
        if current.role == "admin":
            case = await session.get(Case, case_id)
            if case is None:
                raise NotFoundError("Case not found")
            return CaseContext(user=current, case=case, case_role=CaseRole.LEAD.value)

        case, case_role = await _load_membership(session, case_id, current.id)
        from app.auth.rbac import CASE_APPROVE_ROLES, CASE_WRITE_ROLES

        if write and CaseRole(case_role) not in CASE_WRITE_ROLES:
            raise AuthorizationError("Write access required on this case")
        if approve and CaseRole(case_role) not in CASE_APPROVE_ROLES:
            raise AuthorizationError("Approval access required on this case")
        return CaseContext(user=current, case=case, case_role=case_role)

    return _dep
