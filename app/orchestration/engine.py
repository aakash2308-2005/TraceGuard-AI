"""Investigation orchestration engine.

Implements the node sequence from design section 2.8 as an explicit, checkpointed
async state machine. After each node the state is persisted (checkpoint) so a
crash can resume from the last good step. Parallel agents are wrapped with
per-agent timeout, bounded retry, and AgentExecution records.

The automatic flow stops at AWAITING_REVIEW (human-in-the-loop). The report
draft and final approval are handled by M8 endpoints; the Defense re-challenge
loop is bounded by ``defense_max_rounds`` (design 2.8).
"""

import asyncio
import uuid
from datetime import datetime, timezone

from app.agents.base import Agent
from app.agents.registry import build_content_agent, build_parallel_agents
from app.config import get_settings
from app.observability.logging import get_logger, investigation_id_var
from app.observability.metrics import AGENT_DURATION
from app.orchestration.repository import RunRepository
from app.orchestration.state import (
    AgentResult,
    ContradictionItem,
    IndicatorRef,
    InvestigationState,
    InvestigationStatus,
    StepError,
)
from app.persistence.postgres.database import get_sessionmaker

logger = get_logger("orchestrator")

# Linear phases executed automatically before the human review gate.
_AUTO_PHASES: list[InvestigationStatus] = [
    InvestigationStatus.VALIDATING,
    InvestigationStatus.HASHING,
    InvestigationStatus.PLANNING,
    InvestigationStatus.AGENTS_RUNNING,
    InvestigationStatus.NORMALIZING,
    InvestigationStatus.GRAPHING,
    InvestigationStatus.TIMELINE,
    InvestigationStatus.DEFENSE,
    InvestigationStatus.CONFIDENCE,
    InvestigationStatus.REPORT_DRAFT,
]


class Orchestrator:
    """Drives an investigation through its phases with checkpointing."""

    def __init__(self, run_id: uuid.UUID) -> None:
        self._run_id = run_id
        self._settings = get_settings()
        # A single AsyncSession is shared across the (parallel) agent coroutines.
        # SQLAlchemy forbids overlapping flushes, so all writes taken during the
        # parallel phase are serialized behind this lock.
        self._db_write_lock = asyncio.Lock()

    async def run(self) -> None:
        """Entry point for background execution. Resumes from last checkpoint."""
        investigation_id_var.set(str(self._run_id))
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            repo = RunRepository(session)
            state = await repo.load_state(self._run_id)
            if state is None:
                logger.error("run_state_missing", run_id=str(self._run_id))
                return

            try:
                await self._drive(state, repo, session)
            except Exception as exc:  # noqa: BLE001 - top-level safety net
                logger.error("orchestration_failed", error=str(exc))
                state.status = InvestigationStatus.FAILED
                state.errors.append(StepError(node="engine", message=str(exc), retriable=False))
                await repo.save_state(self._run_id, state)
                await session.commit()

    async def _drive(
        self, state: InvestigationState, repo: RunRepository, session
    ) -> None:
        """Execute remaining phases from the current status."""
        # Determine where to resume: phases after the current status.
        start_index = self._resume_index(state.status)

        for phase in _AUTO_PHASES[start_index:]:
            if await self._is_cancelled(state, repo):
                state.status = InvestigationStatus.CANCELLED
                await repo.save_state(self._run_id, state)
                await session.commit()
                logger.info("investigation_cancelled", run_id=str(self._run_id))
                return

            state.status = phase
            await self._run_phase(phase, state, repo, session)

            # After confidence, mirror structured results into relational tables
            # so the API and reports can query them without parsing JSON.
            if phase == InvestigationStatus.CONFIDENCE:
                await self._persist_findings(state, session)

            # Checkpoint after every phase.
            await repo.save_state(self._run_id, state)
            await session.commit()
            logger.info("phase_complete", phase=phase.value, run_id=str(self._run_id))

        # Human-in-the-loop gate.
        state.status = InvestigationStatus.AWAITING_REVIEW
        await repo.save_state(self._run_id, state)
        await session.commit()
        logger.info("awaiting_review", run_id=str(self._run_id))

    async def _persist_findings(self, state: InvestigationState, session) -> None:
        """Best-effort mirror of findings/contradictions/confidence to Postgres."""
        try:
            from app.services.findings_service import FindingsPersistenceService

            service = FindingsPersistenceService(session)
            await service.persist(run_id=self._run_id, state=state)
        except Exception as exc:  # noqa: BLE001
            logger.warning("findings_persist_failed", error=str(exc))

    def _resume_index(self, status: InvestigationStatus) -> int:
        if status in (InvestigationStatus.CREATED,):
            return 0
        if status in _AUTO_PHASES:
            # Resume from the phase that was in progress (re-run is idempotent).
            return _AUTO_PHASES.index(status)
        return 0

    async def _is_cancelled(self, state: InvestigationState, repo: RunRepository) -> bool:
        fresh = await repo.load_state(self._run_id)
        if fresh and fresh.cancel_requested:
            state.cancel_requested = True
            return True
        return False

    async def _run_phase(
        self,
        phase: InvestigationStatus,
        state: InvestigationState,
        repo: RunRepository,
        session,
    ) -> None:
        if phase == InvestigationStatus.VALIDATING:
            self._node_validate(state)
        elif phase == InvestigationStatus.HASHING:
            self._node_hashing(state)
        elif phase == InvestigationStatus.PLANNING:
            self._node_planning(state)
        elif phase == InvestigationStatus.AGENTS_RUNNING:
            await self._node_agents(state, repo, session)
        elif phase == InvestigationStatus.NORMALIZING:
            self._node_normalize(state)
        elif phase == InvestigationStatus.GRAPHING:
            await self._node_graph(state)
        elif phase == InvestigationStatus.TIMELINE:
            self._node_timeline(state)
        elif phase == InvestigationStatus.DEFENSE:
            await self._node_defense(state)
        elif phase == InvestigationStatus.CONFIDENCE:
            await self._node_confidence(state)
        elif phase == InvestigationStatus.REPORT_DRAFT:
            self._node_report_draft(state)

    # --- Node implementations ---

    def _node_validate(self, state: InvestigationState) -> None:
        if not state.indicators and not state.files:
            raise ValueError("Investigation has no evidence to analyze")

    def _node_hashing(self, state: InvestigationState) -> None:
        # Files are hashed at upload (M3). Record that hashes are present.
        missing = [f.filename for f in state.files if not f.sha256]
        if missing:
            state.errors.append(
                StepError(node="hashing", message=f"missing hashes: {missing}", retriable=False)
            )

    def _node_planning(self, state: InvestigationState) -> None:
        # Form an initial hypothesis statement from the evidence set. Real agents
        # refine this; here it is explicitly a hypothesis (not a fact).
        indicator_values = [i.value for i in state.indicators]
        if indicator_values:
            state.hypothesis = (
                "The submitted indicators and files may be associated with a single "
                f"actor or coordinated activity: {', '.join(indicator_values[:5])}."
            )
        else:
            state.hypothesis = (
                "The submitted files may be related to a single actor or event."
            )

    async def _node_agents(
        self, state: InvestigationState, repo: RunRepository, session
    ) -> None:
        """Run data-gathering agents with timeout + retry.

        The Content Analysis Agent runs first, serially, so identifiers it finds
        inside uploaded files are registered as case indicators before the
        parallel OSINT/Metadata/Crypto agents correlate them in the same run.
        """
        content_agent = build_content_agent()
        content_result = await self._run_agent_with_controls(content_agent, state, repo)
        state.agent_results[content_result.agent_name] = content_result
        if content_result.status == "completed":
            registered = await self._register_extracted_indicators(
                state, session, content_result
            )
            if registered:
                logger.info(
                    "extracted_indicators_registered",
                    run_id=str(self._run_id),
                    count=registered,
                )

        agents = build_parallel_agents()
        tasks = [self._run_agent_with_controls(agent, state, repo) for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        for result in results:
            state.agent_results[result.agent_name] = result
        # If every agent (including content extraction) failed, the phase failed.
        all_results = [content_result, *results]
        if all_results and all(r.status == "failed" for r in all_results):
            raise ValueError("All data-gathering agents failed")

    async def _register_extracted_indicators(
        self, state: InvestigationState, session, result: AgentResult
    ) -> int:
        """Promote identifiers found in file content to case indicators.

        New values are stored as ordinary indicator evidence (auditable, and
        normalized exactly like manual submissions) and appended to the run
        state. Idempotent: values already in the state or the case are skipped,
        so a resumed/re-run agents phase never duplicates them.
        """
        from sqlalchemy import select

        from app.domain.errors import ValidationError
        from app.domain.indicators import normalize_indicator
        from app.persistence.postgres.models import EvidenceItem
        from app.services.audit_service import AuditService

        known = {(i.indicator_type, i.value) for i in state.indicators}
        candidates: dict[tuple[str, str], str] = {}  # (type, value) -> source filename
        for finding in result.findings:
            filename = finding.get("filename", "file")
            for item in finding.get("indicators", []):
                itype = item.get("indicator_type", "")
                try:
                    value = normalize_indicator(itype, item.get("value", ""))
                except ValidationError:
                    continue
                key = (itype, value)
                if key in known or key in candidates:
                    continue
                candidates[key] = filename
        if not candidates:
            return 0

        # Drop anything already persisted for this case.
        case_id = uuid.UUID(state.case_id)
        existing = await session.execute(
            select(EvidenceItem.indicator_type, EvidenceItem.indicator_value).where(
                EvidenceItem.case_id == case_id,
                EvidenceItem.indicator_value.in_([v for _t, v in candidates]),
            )
        )
        for itype, value in existing.all():
            candidates.pop((itype, value), None)
        if not candidates:
            return 0

        # Bound side effects: cap how many new indicators one run can create, so
        # a single evidence file cannot trigger unbounded rows/lookups.
        limit = self._settings.content_max_indicators_per_run
        if len(candidates) > limit:
            candidates = dict(sorted(candidates.items())[:limit])
            logger.warning(
                "extracted_indicators_truncated",
                run_id=str(self._run_id),
                kept=limit,
            )

        actor_id = uuid.UUID(state.started_by)
        now = datetime.now(timezone.utc)
        for (itype, value), filename in candidates.items():
            evidence = EvidenceItem(
                case_id=case_id,
                type="indicator",
                indicator_type=itype,
                indicator_value=value,
                source=f"content_extraction:{filename}",
                source_retrieved_at=now,
                verification_status="unverified",
                uploaded_by=actor_id,
                processing_history=[
                    {"step": "extracted_from_file", "filename": filename, "at": now.isoformat()}
                ],
                chain_of_custody=[
                    {
                        "action": "extract_identifier",
                        "actor_id": "system:content_agent",
                        "at": now.isoformat(),
                        "filename": filename,
                        "indicator": value,
                    }
                ],
            )
            session.add(evidence)
            await session.flush()
            state.indicators.append(
                IndicatorRef(
                    evidence_id=str(evidence.id),
                    indicator_type=itype,
                    value=value,
                )
            )

        await AuditService(session).record(
            "evidence.indicator_extracted",
            actor_id=actor_id,
            case_id=case_id,
            detail={"run_id": str(self._run_id), "count": len(candidates)},
        )
        return len(candidates)

    async def _run_agent_with_controls(
        self, agent: Agent, state: InvestigationState, repo: RunRepository
    ) -> AgentResult:
        """Run one agent with timeout, bounded retry, timing, and persistence."""
        max_retries = self._settings.agent_max_retries
        timeout = self._settings.agent_timeout_seconds
        attempt = 0
        last_error: str | None = None

        while attempt <= max_retries:
            attempt += 1
            start = datetime.now(timezone.utc)
            try:
                result = await asyncio.wait_for(agent.run(state), timeout=timeout)
                duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
                AGENT_DURATION.labels(agent.name).observe(duration_ms / 1000)
                async with self._db_write_lock:
                    await repo.record_agent_execution(
                        run_id=self._run_id,
                        agent_name=agent.name,
                        status=result.status,
                        duration_ms=duration_ms,
                    )
                return result
            except asyncio.TimeoutError:
                last_error = "timeout"
                logger.warning("agent_timeout", agent=agent.name, attempt=attempt)
            except Exception as exc:  # noqa: BLE001 - record and maybe retry
                last_error = str(exc)
                logger.warning("agent_error", agent=agent.name, attempt=attempt, error=last_error)

        duration_ms = 0
        async with self._db_write_lock:
            await repo.record_agent_execution(
                run_id=self._run_id,
                agent_name=agent.name,
                status="failed",
                duration_ms=duration_ms,
                error={"message": last_error},
            )
        return AgentResult(
            agent_name=agent.name,
            status="failed",
            limitations=[f"agent_failed:{last_error}"],
        )

    def _node_normalize(self, state: InvestigationState) -> None:
        """Flatten agent findings into the state's findings list."""
        findings: list[dict] = []
        for result in state.agent_results.values():
            for f in result.findings:
                findings.append({**f, "agent_name": result.agent_name})
        state.findings = findings

    async def _node_graph(self, state: InvestigationState) -> None:
        """Build a provenance-aware relationship graph in Neo4j.

        Degrades gracefully: if Neo4j is unavailable, records a limitation and a
        best-effort summary rather than failing the whole investigation.
        """
        try:
            from app.orchestration.graph_builder import build_graph
            from app.persistence.neo4j.database import get_graph_driver
            from app.persistence.neo4j.graph_repository import GraphRepository

            repo = GraphRepository(get_graph_driver())
            await repo.apply_constraints()
            state.graph_summary = await build_graph(state, repo)
        except Exception as exc:  # noqa: BLE001 - graceful degradation (REL-002)
            logger.warning("graph_build_failed", error=str(exc))
            state.errors.append(
                StepError(node="graphing", message=f"graph_unavailable:{exc}", retriable=True)
            )
            state.graph_summary = {
                "nodes": len(state.indicators) + len(state.files),
                "edges": 0,
                "note": "graph_backend_unavailable",
            }

    def _node_timeline(self, state: InvestigationState) -> None:
        """Assemble a chronological timeline from timestamped evidence/findings."""
        events: list[dict] = []
        for f in state.findings:
            ts = f.get("timestamp")
            if ts:
                events.append({"at": ts, "label": f.get("summary", "finding"), "source": f.get("agent_name")})
        events.sort(key=lambda e: e["at"])
        state.timeline = events

    async def _node_defense(self, state: InvestigationState) -> None:
        """Run the Defense Agent. Bounded by defense_max_rounds (design 2.8).

        The agent runs once automatically here. A human reviewer may trigger at
        most ``defense_max_rounds`` total rounds via the review endpoint (M8).
        """
        if state.defense_rounds >= self._settings.defense_max_rounds:
            state.errors.append(
                StepError(
                    node="defense",
                    message="defense_max_rounds_reached",
                    retriable=False,
                )
            )
            return
        state.defense_rounds += 1
        from app.agents.registry import build_defense_agent

        agent = build_defense_agent()
        result = await agent.run(state)
        state.agent_results[agent.name] = result
        contradictions = result.extra.get("contradictions", [])
        state.contradictions = [ContradictionItem(**c) for c in contradictions]

    async def _node_confidence(self, state: InvestigationState) -> None:
        """Compute a transparent, deterministic confidence assessment.

        Scoring arithmetic lives in the Confidence Engine (pure code); the LLM is
        never used to produce the number. Insufficient evidence yields an explicit
        insufficient band rather than a fabricated score.

        A supplementary IBM Z score is fetched and attached (clearly labelled real
        or simulated). It degrades gracefully: if unavailable, confidence is still
        computed and a limitation is recorded.
        """
        from app.agents.confidence_engine import compute_confidence

        ibmz_score: dict | None = None
        try:
            from app.integrations.ibmz.adapter import get_ibmz_adapter
            from app.integrations.ibmz.features import extract_features

            adapter = get_ibmz_adapter()
            features = extract_features(state)
            result = await adapter.score(
                investigation_id=str(self._run_id), features=features
            )
            ibmz_score = result.to_dict()
        except Exception as exc:  # noqa: BLE001 - never block confidence
            logger.warning("ibmz_score_skipped", error=str(exc))
            ibmz_score = {
                "score": None,
                "simulated": False,
                "available": False,
                "detail": f"IBM Z scoring skipped: {type(exc).__name__}",
                "source": "ibmz",
            }

        state.confidence = compute_confidence(state, ibmz_score=ibmz_score)

    def _node_report_draft(self, state: InvestigationState) -> None:
        """Mark that a draft can be generated (report content built in M8)."""
        # No-op structurally; the report is generated on demand via the M8 endpoint.
        return


async def start_investigation(run_id: uuid.UUID) -> None:
    """Background task entry point used by the API layer."""
    orchestrator = Orchestrator(run_id)
    await orchestrator.run()
