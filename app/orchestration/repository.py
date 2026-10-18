"""Persistence helpers for investigation runs and agent executions.

State is written to ``investigation_runs.state`` after each node, which serves
as the checkpoint. Recovery reloads the last persisted state and resumes from
its ``status``.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestration.state import InvestigationState, InvestigationStatus
from app.persistence.postgres.models import AgentExecution, InvestigationRun


class RunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        # Agents run concurrently (asyncio.gather) but share this repository and
        # its AsyncSession. Two tasks flushing at the same time raise
        # "Session is already flushing", which the engine misreads as an agent
        # failure and retries (duplicate side effects, or a dropped agent result
        # once retries are exhausted). All writes are serialized through this
        # lock so only one flush can be in flight at a time.
        self._write_lock = asyncio.Lock()

    async def load_state(self, run_id: uuid.UUID) -> InvestigationState | None:
        run = await self._session.get(InvestigationRun, run_id)
        if run is None or not run.state:
            return None
        return InvestigationState.from_json(run.state)

    async def save_state(self, run_id: uuid.UUID, state: InvestigationState) -> None:
        """Persist the state snapshot (checkpoint) and mirror status."""
        async with self._write_lock:
            run = await self._session.get(InvestigationRun, run_id)
            if run is None:
                return
            run.state = state.to_json()
            run.status = state.status.value
            if state.status in (
                InvestigationStatus.APPROVED,
                InvestigationStatus.FAILED,
                InvestigationStatus.CANCELLED,
                InvestigationStatus.AWAITING_REVIEW,
            ):
                if state.status != InvestigationStatus.AWAITING_REVIEW:
                    run.completed_at = datetime.now(timezone.utc)
            await self._session.flush()

    async def record_agent_execution(
        self,
        *,
        run_id: uuid.UUID,
        agent_name: str,
        status: str,
        duration_ms: int,
        tool_calls: list | None = None,
        error: dict | None = None,
    ) -> None:
        execution = AgentExecution(
            run_id=run_id,
            agent_name=agent_name,
            status=status,
            duration_ms=duration_ms,
            tool_calls=tool_calls or [],
            error=error,
        )
        async with self._write_lock:
            self._session.add(execution)
            await self._session.flush()

    async def list_agent_executions(self, run_id: uuid.UUID) -> list[AgentExecution]:
        result = await self._session.execute(
            select(AgentExecution)
            .where(AgentExecution.run_id == run_id)
            .order_by(AgentExecution.created_at)
        )
        return list(result.scalars().all())

    async def set_cancel_requested(self, run_id: uuid.UUID) -> bool:
        """Flag a run for cooperative cancellation. Returns True if updated."""
        run = await self._session.get(InvestigationRun, run_id)
        if run is None:
            return False
        state = run.state or {}
        state["cancel_requested"] = True
        run.state = state
        await self._session.flush()
        return True
