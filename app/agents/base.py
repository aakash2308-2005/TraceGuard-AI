"""Shared agent contract.

Every agent exposes an async ``run(state) -> AgentResult`` method and a stable
``name``. Agents call deterministic tools for verifiable work and the LLM
provider only for reasoning. The orchestrator wraps each run with timing,
timeout, retry, and AgentExecution persistence; agents themselves stay focused
on their domain logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.orchestration.state import AgentResult, InvestigationState


class Agent(ABC):
    """Abstract base for all specialized agents."""

    #: Stable identifier used as the idempotency key and in execution records.
    name: str = "agent"

    @abstractmethod
    async def run(self, state: InvestigationState) -> AgentResult:
        """Execute the agent against the current investigation state."""
        raise NotImplementedError
