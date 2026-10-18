"""Unit tests for orchestration state and node logic (no DB required)."""

import asyncio
import uuid

import pytest

from app.orchestration.engine import _AUTO_PHASES, Orchestrator
from app.orchestration.repository import RunRepository
from app.orchestration.state import (
    AgentResult,
    IndicatorRef,
    InvestigationState,
    InvestigationStatus,
)


def _make_state(**kwargs) -> InvestigationState:
    return InvestigationState(
        investigation_id=str(uuid.uuid4()),
        case_id=str(uuid.uuid4()),
        started_by=str(uuid.uuid4()),
        **kwargs,
    )


def test_state_json_roundtrip():
    state = _make_state(
        indicators=[IndicatorRef(evidence_id="e1", indicator_type="email", value="a@b.com")]
    )
    data = state.to_json()
    restored = InvestigationState.from_json(data)
    assert restored.indicators[0].value == "a@b.com"
    assert restored.status == InvestigationStatus.CREATED


def test_validate_node_requires_evidence():
    orch = Orchestrator(uuid.uuid4())
    empty = _make_state()
    with pytest.raises(ValueError):
        orch._node_validate(empty)


def test_planning_sets_hypothesis_as_hypothesis():
    orch = Orchestrator(uuid.uuid4())
    state = _make_state(
        indicators=[IndicatorRef(evidence_id="e1", indicator_type="username", value="shadowfox")]
    )
    orch._node_planning(state)
    assert state.hypothesis is not None
    assert "shadowfox" in state.hypothesis


def test_normalize_flattens_agent_findings():
    orch = Orchestrator(uuid.uuid4())
    state = _make_state()
    state.agent_results["osint"] = AgentResult(
        agent_name="osint",
        status="completed",
        findings=[{"summary": "domain registered", "epistemic_status": "fact"}],
    )
    orch._node_normalize(state)
    assert len(state.findings) == 1
    assert state.findings[0]["agent_name"] == "osint"


def test_confidence_defaults_to_insufficient():
    orch = Orchestrator(uuid.uuid4())
    state = _make_state()

    asyncio.run(orch._node_confidence(state))
    assert state.confidence is not None
    assert state.confidence.band == "insufficient"
    assert state.confidence.score is None


def test_resume_index_from_created_is_zero():
    orch = Orchestrator(uuid.uuid4())
    assert orch._resume_index(InvestigationStatus.CREATED) == 0


def test_resume_index_from_midphase():
    orch = Orchestrator(uuid.uuid4())
    idx = orch._resume_index(InvestigationStatus.DEFENSE)
    assert _AUTO_PHASES[idx] == InvestigationStatus.DEFENSE


def test_timeline_sorts_events():
    orch = Orchestrator(uuid.uuid4())
    state = _make_state()
    state.findings = [
        {"timestamp": "2024-02-01T00:00:00Z", "summary": "b", "agent_name": "osint"},
        {"timestamp": "2024-01-01T00:00:00Z", "summary": "a", "agent_name": "crypto"},
    ]
    orch._node_timeline(state)
    assert [e["at"] for e in state.timeline] == [
        "2024-01-01T00:00:00Z",
        "2024-02-01T00:00:00Z",
    ]


class _InterleavingSession:
    """Stub that reproduces SQLAlchemy's concurrent-flush failure.

    Raises "Session is already flushing" if flush() is re-entered while a
    previous flush is still yielding, exactly like the real AsyncSession does
    when parallel agents record executions on a shared session.
    """

    def __init__(self) -> None:
        self.flushing = False
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        if self.flushing:
            raise RuntimeError("Session is already flushing")
        self.flushing = True
        await asyncio.sleep(0)  # yield so an unguarded concurrent flush collides
        self.flushing = False


async def test_parallel_execution_records_never_flush_concurrently():
    """Parallel agents recording executions must not overlap flushes (bug that
    made agents retry and lose findings)."""
    repo = RunRepository(_InterleavingSession())
    await asyncio.gather(
        *[
            repo.record_agent_execution(
                run_id=uuid.uuid4(),
                agent_name=f"agent{i}",
                status="completed",
                duration_ms=1,
            )
            for i in range(5)
        ]
    )
    assert len(repo._session.added) == 5
