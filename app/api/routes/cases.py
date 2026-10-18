"""Case management and membership endpoints."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CaseContext,
    CurrentUser,
    get_current_user,
    require_case_member,
    require_permission,
)
from app.api.schemas import (
    AuditEventResponse,
    CaseCreate,
    CaseResponse,
    CaseUpdate,
    MemberAdd,
    MemberResponse,
)
from app.persistence.postgres.database import get_db_session
from app.services.case_service import CaseService

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CaseCreate,
    current: CurrentUser = Depends(require_permission("create_case")),
    session: AsyncSession = Depends(get_db_session),
) -> CaseResponse:
    service = CaseService(session)
    case = await service.create_case(
        case_identifier=body.case_identifier,
        title=body.title,
        description=body.description,
        creator_id=current.id,
        case_role=body.case_role,
    )
    resp = CaseResponse.model_validate(case)
    resp.my_case_role = body.case_role
    return resp


@router.get("", response_model=list[CaseResponse])
async def list_cases(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[CaseResponse]:
    service = CaseService(session)
    rows = await service.list_cases_for_user(current.id, is_admin=current.role == "admin")
    out: list[CaseResponse] = []
    for case, case_role in rows:
        resp = CaseResponse.model_validate(case)
        resp.my_case_role = case_role
        out.append(resp)
    return out


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: uuid.UUID,
    ctx: CaseContext = Depends(require_case_member()),
) -> CaseResponse:
    resp = CaseResponse.model_validate(ctx.case)
    resp.my_case_role = ctx.case_role
    return resp


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: uuid.UUID,
    body: CaseUpdate,
    ctx: CaseContext = Depends(require_case_member(write=True)),
    session: AsyncSession = Depends(get_db_session),
) -> CaseResponse:
    service = CaseService(session)
    case = await service.update_case(
        ctx.case,
        title=body.title,
        description=body.description,
        status=body.status,
        actor_id=ctx.user.id,
    )
    resp = CaseResponse.model_validate(case)
    resp.my_case_role = ctx.case_role
    return resp


@router.get("/{case_id}/members", response_model=list[MemberResponse])
async def list_members(
    case_id: uuid.UUID,
    ctx: CaseContext = Depends(require_case_member()),
    session: AsyncSession = Depends(get_db_session),
) -> list[MemberResponse]:
    service = CaseService(session)
    rows = await service.list_members(case_id)
    return [
        MemberResponse(user_id=m.user_id, username=u.username, case_role=m.case_role)
        for m, u in rows
    ]


@router.post("/{case_id}/members", response_model=MemberResponse, status_code=201)
async def add_member(
    case_id: uuid.UUID,
    body: MemberAdd,
    ctx: CaseContext = Depends(require_case_member(write=True)),
    session: AsyncSession = Depends(get_db_session),
) -> MemberResponse:
    service = CaseService(session)
    membership = await service.add_member(
        case_id=case_id, user_id=body.user_id, case_role=body.case_role, actor_id=ctx.user.id
    )
    from app.persistence.postgres.models import User

    db_user = await session.get(User, body.user_id)
    return MemberResponse(
        user_id=membership.user_id,
        username=db_user.username if db_user else "",
        case_role=membership.case_role,
    )


@router.delete("/{case_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    case_id: uuid.UUID,
    user_id: uuid.UUID,
    ctx: CaseContext = Depends(require_case_member(write=True)),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    service = CaseService(session)
    await service.remove_member(case_id=case_id, user_id=user_id, actor_id=ctx.user.id)


@router.get("/{case_id}/audit", response_model=list[AuditEventResponse])
async def case_audit(
    case_id: uuid.UUID,
    ctx: CaseContext = Depends(require_case_member()),
    session: AsyncSession = Depends(get_db_session),
) -> list[AuditEventResponse]:
    """Return audit events for a case (members with audit visibility)."""
    from sqlalchemy import select

    from app.persistence.postgres.models import AuditEvent

    result = await session.execute(
        select(AuditEvent)
        .where(AuditEvent.case_id == case_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(500)
    )
    return [AuditEventResponse.model_validate(e) for e in result.scalars().all()]
