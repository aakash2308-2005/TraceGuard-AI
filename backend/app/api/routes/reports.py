"""Report endpoints: generate draft, fetch, and approve (human review gate)."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ReportContext,
    RunContext,
    require_report_access,
    require_run_access,
)
from app.api.schemas import ReportResponse
from app.persistence.postgres.database import get_db_session
from app.services.report_service import ReportService

# Draft generation is keyed by investigation id.
run_router = APIRouter(prefix="/investigations/{investigation_id}", tags=["reports"])
# Fetch/approve are keyed by report id.
router = APIRouter(prefix="/reports", tags=["reports"])


@run_router.post("/report", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_report(
    investigation_id: uuid.UUID,
    rc: RunContext = Depends(require_run_access(write=True)),
    session: AsyncSession = Depends(get_db_session),
) -> ReportResponse:
    """Generate (or regenerate) a draft report for an investigation."""
    service = ReportService(session)
    report = await service.generate_draft(
        run_id=investigation_id, case_id=rc.case_id, actor_id=rc.user.id
    )
    return ReportResponse.model_validate(report)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: uuid.UUID,
    ctx: ReportContext = Depends(require_report_access()),
    session: AsyncSession = Depends(get_db_session),
) -> ReportResponse:
    service = ReportService(session)
    report, _case_id = await service.get_report(report_id)
    return ReportResponse.model_validate(report)


@router.post("/{report_id}/approve", response_model=ReportResponse)
async def approve_report(
    report_id: uuid.UUID,
    ctx: ReportContext = Depends(require_report_access(approve=True)),
    session: AsyncSession = Depends(get_db_session),
) -> ReportResponse:
    """Approve/finalize a draft report (reviewer/lead only)."""
    service = ReportService(session)
    report = await service.approve(
        report_id=report_id, case_id=ctx.case_id, actor_id=ctx.user.id
    )
    return ReportResponse.model_validate(report)
