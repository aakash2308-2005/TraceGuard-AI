"""Persist investigation findings, hypothesis, contradictions, and confidence.

The authoritative snapshot lives in ``investigation_runs.state`` (JSON). This
service mirrors the structured results into relational tables so they can be
queried, joined, and referenced by reports and the API without parsing JSON.

Idempotent: existing rows for the run are cleared and rewritten so re-running a
phase does not duplicate records.
"""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.logging import get_logger
from app.orchestration.state import InvestigationState
from app.persistence.postgres.models import (
    ConfidenceAssessment,
    Contradiction,
    ExternalSourceRef,
    Finding,
    Hypothesis,
)

logger = get_logger("findings_service")


class FindingsPersistenceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def persist(self, *, run_id: uuid.UUID, state: InvestigationState) -> None:
        """Mirror findings/hypothesis/contradictions/confidence into tables."""
        await self._clear(run_id)

        # Findings + their external source refs.
        for f in state.findings:
            finding = Finding(
                run_id=run_id,
                agent_name=f.get("agent_name", "unknown"),
                claim_type=f.get("claim_type", "general"),
                epistemic_status=f.get("epistemic_status", "inference"),
                payload=f,
            )
            self._session.add(finding)
            await self._session.flush()
            data = f.get("data", {})
            source_name = data.get("source") if isinstance(data, dict) else None
            if source_name:
                self._session.add(
                    ExternalSourceRef(
                        finding_id=finding.id,
                        source_name=source_name,
                        url=data.get("url"),
                        reliability_tier=data.get("reliability_tier", "unknown"),
                    )
                )

        # Hypothesis + contradictions + confidence (one hypothesis per run here).
        hypothesis = None
        if state.hypothesis:
            hypothesis = Hypothesis(run_id=run_id, statement=state.hypothesis, status="open")
            self._session.add(hypothesis)
            await self._session.flush()

            for c in state.contradictions:
                self._session.add(
                    Contradiction(
                        hypothesis_id=hypothesis.id,
                        kind=c.kind,
                        description=c.description,
                        basis=c.basis,
                        refs=c.refs,
                    )
                )

            if state.confidence:
                self._session.add(
                    ConfidenceAssessment(
                        hypothesis_id=hypothesis.id,
                        score=state.confidence.score,
                        band=state.confidence.band,
                        factors=state.confidence.factors,
                        limitations=state.confidence.limitations,
                    )
                )

        await self._session.flush()
        logger.info("findings_persisted", run_id=str(run_id), findings=len(state.findings))

    async def _clear(self, run_id: uuid.UUID) -> None:
        # Delete dependent hypotheses (cascades to contradictions/confidence) and findings.
        result = await self._session.execute(
            select(Hypothesis.id).where(Hypothesis.run_id == run_id)
        )
        hyp_ids = [r[0] for r in result.all()]
        if hyp_ids:
            await self._session.execute(
                delete(Contradiction).where(Contradiction.hypothesis_id.in_(hyp_ids))
            )
            await self._session.execute(
                delete(ConfidenceAssessment).where(
                    ConfidenceAssessment.hypothesis_id.in_(hyp_ids)
                )
            )
            await self._session.execute(delete(Hypothesis).where(Hypothesis.run_id == run_id))
        # Findings' source refs cascade via FK ondelete=CASCADE.
        await self._session.execute(delete(Finding).where(Finding.run_id == run_id))
        await self._session.flush()
