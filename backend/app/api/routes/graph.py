"""Graph and timeline query endpoints (case-scoped).

The relationship graph is read from Neo4j and scoped by case. If Neo4j is
unavailable, the endpoint returns an empty graph with an explanatory note rather
than failing (graceful degradation).
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CaseContext, require_case_member
from app.api.schemas import GraphResponse, TimelineResponse
from app.observability.logging import get_logger
from app.persistence.postgres.database import get_db_session

router = APIRouter(prefix="/cases/{case_id}", tags=["graph"])
logger = get_logger("graph_api")


@router.get("/graph", response_model=GraphResponse)
async def get_graph(
    case_id: uuid.UUID,
    ctx: CaseContext = Depends(require_case_member()),
) -> GraphResponse:
    """Return the provenance-aware relationship graph for a case."""
    try:
        from app.persistence.neo4j.database import get_graph_driver
        from app.persistence.neo4j.graph_repository import GraphRepository

        repo = GraphRepository(get_graph_driver())
        data = await repo.get_case_graph(str(case_id))
        return GraphResponse(nodes=data["nodes"], edges=data["edges"])
    except Exception as exc:  # noqa: BLE001 - degrade gracefully
        logger.warning("graph_query_failed", error=str(exc))
        return GraphResponse(nodes=[], edges=[], note="graph_backend_unavailable")


@router.get("/timeline", response_model=TimelineResponse)
async def get_case_timeline(
    case_id: uuid.UUID,
    ctx: CaseContext = Depends(require_case_member()),
    session: AsyncSession = Depends(get_db_session),
) -> TimelineResponse:
    """Return a merged chronological timeline across the case's investigations."""
    from app.orchestration.state import InvestigationState
    from app.persistence.postgres.models import InvestigationRun

    result = await session.execute(
        select(InvestigationRun).where(InvestigationRun.case_id == case_id)
    )
    events: list[dict] = []
    for run in result.scalars().all():
        if not run.state:
            continue
        try:
            state = InvestigationState.from_json(run.state)
        except Exception:  # noqa: BLE001
            continue
        for ev in state.timeline:
            events.append({**ev, "investigation_id": str(run.id)})
    events.sort(key=lambda e: e.get("at", ""))
    return TimelineResponse(events=events)
