"""Investigation lifecycle service: create, status, cancel, findings."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import NotFoundError, ValidationError
from app.observability.logging import get_logger
from app.orchestration.repository import RunRepository
from app.orchestration.state import (
    FileRef,
    IndicatorRef,
    InvestigationState,
    InvestigationStatus,
)
from app.persistence.postgres.models import EvidenceItem, InvestigationRun
from app.services.audit_service import AuditService

logger = get_logger("investigation")


class InvestigationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._audit = AuditService(session)
        self._runs = RunRepository(session)

    async def create_investigation(
        self, *, case_id: uuid.UUID, actor_id: uuid.UUID
    ) -> InvestigationRun:
        """Create a run and snapshot current case evidence into its state."""
        result = await self._session.execute(
            select(EvidenceItem).where(EvidenceItem.case_id == case_id)
        )
        evidence = list(result.scalars().all())
        if not evidence:
            raise ValidationError("Cannot start an investigation with no evidence")

        indicators = [
            IndicatorRef(
                evidence_id=str(e.id),
                indicator_type=e.indicator_type or "",
                value=e.indicator_value or "",
            )
            for e in evidence
            if e.type == "indicator"
        ]
        files = [
            FileRef(
                evidence_id=str(e.id),
                filename=e.original_filename or "file",
                sha256=e.sha256,
                mime_type=e.mime_type,
            )
            for e in evidence
            if e.type == "file"
        ]

        run = InvestigationRun(
            case_id=case_id,
            status=InvestigationStatus.CREATED.value,
            started_by=actor_id,
            state={},
        )
        self._session.add(run)
        await self._session.flush()

        state = InvestigationState(
            investigation_id=str(run.id),
            case_id=str(case_id),
            started_by=str(actor_id),
            status=InvestigationStatus.CREATED,
            indicators=indicators,
            files=files,
        )
        run.state = state.to_json()
        await self._session.flush()

        await self._audit.record(
            "investigation.created",
            actor_id=actor_id,
            case_id=case_id,
            detail={
                "investigation_id": str(run.id),
                "indicators": len(indicators),
                "files": len(files),
            },
        )
        logger.info("investigation_created", run_id=str(run.id))
        return run

    async def get_run(self, run_id: uuid.UUID, case_id: uuid.UUID) -> InvestigationRun:
        run = await self._session.get(InvestigationRun, run_id)
        if run is None or run.case_id != case_id:
            raise NotFoundError("Investigation not found")
        return run

    async def cancel(self, *, run_id: uuid.UUID, case_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        run = await self.get_run(run_id, case_id)
        if run.status in (
            InvestigationStatus.APPROVED.value,
            InvestigationStatus.FAILED.value,
            InvestigationStatus.CANCELLED.value,
        ):
            raise ValidationError(f"Cannot cancel a run in status {run.status}")
        await self._runs.set_cancel_requested(run_id)
        await self._audit.record(
            "investigation.cancel_requested",
            actor_id=actor_id,
            case_id=case_id,
            detail={"investigation_id": str(run_id)},
        )

    async def list_agent_executions(self, run_id: uuid.UUID):
        return await self._runs.list_agent_executions(run_id)
