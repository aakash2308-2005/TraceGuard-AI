"""Investigation endpoints: create/start, status, cancel, findings.

Investigations run as in-process background tasks. Creation returns immediately
with status ``created``; the orchestrator advances the run through its phases and
checkpoints state after each phase (recoverable on restart).
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CaseContext,
    RunContext,
    require_case_member,
    require_run_access,
)
from app.api.schemas import (
    AgentExecutionResponse,
    ConfidenceResponse,
    ContradictionResponse,
    FindingResponse,
    InvestigationCreateResponse,
    InvestigationStatusResponse,
    TimelineResponse,
)
from app.orchestration.engine import start_investigation
from app.orchestration.state import InvestigationState
from app.persistence.postgres.database import get_db_session
from app.services.investigation_service import InvestigationService

case_router = APIRouter(prefix="/cases/{case_id}/investigations", tags=["investigations"])
router = APIRouter(prefix="/investigations", tags=["investigations"])


@case_router.post(
    "", response_model=InvestigationCreateResponse, status_code=status.HTTP_201_CREATED
)
async def create_investigation(
    case_id: uuid.UUID,
    background: BackgroundTasks,
    ctx: CaseContext = Depends(require_case_member(write=True)),
    session: AsyncSession = Depends(get_db_session),
) -> InvestigationCreateResponse:
    service = InvestigationService(session)
    run = await service.create_investigation(case_id=case_id, actor_id=ctx.user.id)
    # Commit happens via the session dependency after the handler returns; the
    # background task opens its own session and reads the committed run.
    background.add_task(start_investigation, run.id)
    return InvestigationCreateResponse(id=run.id, case_id=case_id, status=run.status)


def _load_state(run) -> InvestigationState | None:
    if not run.state:
        return None
    try:
        return InvestigationState.from_json(run.state)
    except Exception:  # noqa: BLE001 - tolerate partial early state
        return None


@router.get("/{investigation_id}", response_model=InvestigationStatusResponse)
async def get_status(
    investigation_id: uuid.UUID,
    rc: RunContext = Depends(require_run_access()),
    session: AsyncSession = Depends(get_db_session),
) -> InvestigationStatusResponse:
    service = InvestigationService(session)
    run = await service.get_run(investigation_id, rc.case_id)
    state = _load_state(run)
    executions = await service.list_agent_executions(investigation_id)

    return InvestigationStatusResponse(
        id=run.id,
        case_id=run.case_id,
        status=run.status,
        hypothesis=state.hypothesis if state else None,
        findings_count=len(state.findings) if state else 0,
        contradictions_count=len(state.contradictions) if state else 0,
        confidence_band=(state.confidence.band if state and state.confidence else None),
        timeline_count=len(state.timeline) if state else 0,
        errors=[e.model_dump() for e in state.errors] if state else [],
        agent_executions=[AgentExecutionResponse.model_validate(e) for e in executions],
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.post("/{investigation_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_investigation(
    investigation_id: uuid.UUID,
    rc: RunContext = Depends(require_run_access(write=True)),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = InvestigationService(session)
    await service.cancel(run_id=investigation_id, case_id=rc.case_id, actor_id=rc.user.id)
    return {"status": "cancel_requested"}


@router.get("/{investigation_id}/findings", response_model=list[FindingResponse])
async def get_findings(
    investigation_id: uuid.UUID,
    rc: RunContext = Depends(require_run_access()),
    session: AsyncSession = Depends(get_db_session),
) -> list[FindingResponse]:
    service = InvestigationService(session)
    run = await service.get_run(investigation_id, rc.case_id)
    state = _load_state(run)
    if not state:
        return []
    return [
        FindingResponse(
            agent_name=f.get("agent_name", "unknown"),
            epistemic_status=f.get("epistemic_status", "inference"),
            claim_type=f.get("claim_type"),
            payload=f,
        )
        for f in state.findings
    ]


@router.get("/{investigation_id}/contradictions", response_model=list[ContradictionResponse])
async def get_contradictions(
    investigation_id: uuid.UUID,
    rc: RunContext = Depends(require_run_access()),
    session: AsyncSession = Depends(get_db_session),
) -> list[ContradictionResponse]:
    service = InvestigationService(session)
    run = await service.get_run(investigation_id, rc.case_id)
    state = _load_state(run)
    if not state:
        return []
    return [ContradictionResponse(**c.model_dump()) for c in state.contradictions]


@router.get("/{investigation_id}/confidence", response_model=ConfidenceResponse)
async def get_confidence(
    investigation_id: uuid.UUID,
    rc: RunContext = Depends(require_run_access()),
    session: AsyncSession = Depends(get_db_session),
) -> ConfidenceResponse:
    service = InvestigationService(session)
    run = await service.get_run(investigation_id, rc.case_id)
    state = _load_state(run)
    if not state or not state.confidence:
        return ConfidenceResponse(
            score=None, band="insufficient", factors={}, limitations=["no_assessment_yet"]
        )
    return ConfidenceResponse(**state.confidence.model_dump())


@router.get("/{investigation_id}/timeline", response_model=TimelineResponse)
async def get_timeline(
    investigation_id: uuid.UUID,
    rc: RunContext = Depends(require_run_access()),
    session: AsyncSession = Depends(get_db_session),
) -> TimelineResponse:
    service = InvestigationService(session)
    run = await service.get_run(investigation_id, rc.case_id)
    state = _load_state(run)
    return TimelineResponse(events=state.timeline if state else [])
