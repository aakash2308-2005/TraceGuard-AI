"""Report service: draft generation and human approval (FR-017, FR-018).

Reports are always generated as drafts. Finalization requires an explicit human
approval by a reviewer/lead. The approved content is hashed and the hash is
recorded in the audit log so later tampering is detectable.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.report_generator import ReportGenerator
from app.domain.errors import ConflictError, NotFoundError, ValidationError
from app.observability.logging import get_logger
from app.orchestration.state import InvestigationState, InvestigationStatus
from app.persistence.postgres.models import InvestigationRun, Report
from app.services.audit_service import AuditService

logger = get_logger("report_service")


def _content_hash(content: dict) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class ReportService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._audit = AuditService(session)

    async def generate_draft(
        self, *, run_id: uuid.UUID, case_id: uuid.UUID, actor_id: uuid.UUID
    ) -> Report:
        """Generate (or regenerate) a draft report for an investigation run."""
        run = await self._session.get(InvestigationRun, run_id)
        if run is None or run.case_id != case_id:
            raise NotFoundError("Investigation not found")
        if not run.state:
            raise ValidationError("Investigation has no state to report on")

        state = InvestigationState.from_json(run.state)
        content = await ReportGenerator().generate(state)
        chash = _content_hash(content)

        # Replace any existing draft for this run (idempotent regeneration).
        existing = await self._session.execute(
            select(Report).where(Report.run_id == run_id, Report.status == "draft")
        )
        report = existing.scalar_one_or_none()
        if report is None:
            report = Report(run_id=run_id, status="draft", content=content, content_hash=chash)
            self._session.add(report)
        else:
            report.content = content
            report.content_hash = chash
        await self._session.flush()

        await self._audit.record(
            "report.draft_generated",
            actor_id=actor_id,
            case_id=case_id,
            detail={"report_id": str(report.id), "content_hash": chash},
        )
        logger.info("report_draft_generated", report_id=str(report.id))
        return report

    async def get_report(self, report_id: uuid.UUID) -> tuple[Report, uuid.UUID]:
        """Return a report and its owning case id (for authorization)."""
        report = await self._session.get(Report, report_id)
        if report is None:
            raise NotFoundError("Report not found")
        run = await self._session.get(InvestigationRun, report.run_id)
        if run is None:
            raise NotFoundError("Report not found")
        return report, run.case_id

    async def approve(
        self, *, report_id: uuid.UUID, case_id: uuid.UUID, actor_id: uuid.UUID
    ) -> Report:
        """Finalize a draft report after human review (FR-018)."""
        report = await self._session.get(Report, report_id)
        if report is None:
            raise NotFoundError("Report not found")
        if report.status == "approved":
            raise ConflictError("Report already approved")

        # Re-hash the content at approval time to pin exactly what was approved.
        report.content_hash = _content_hash(report.content)
        report.status = "approved"
        report.approved_by = actor_id
        report.approved_at = datetime.now(timezone.utc)

        # Mark the investigation run approved.
        run = await self._session.get(InvestigationRun, report.run_id)
        if run is not None:
            run.status = InvestigationStatus.APPROVED.value
            state_dict = run.state or {}
            state_dict["status"] = InvestigationStatus.APPROVED.value
            run.state = state_dict
            run.completed_at = datetime.now(timezone.utc)

        await self._session.flush()
        await self._audit.record(
            "report.approved",
            actor_id=actor_id,
            case_id=case_id,
            detail={"report_id": str(report.id), "content_hash": report.content_hash},
        )
        logger.info("report_approved", report_id=str(report.id), approved_by=str(actor_id))
        return report
