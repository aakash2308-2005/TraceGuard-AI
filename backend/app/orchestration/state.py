"""Typed investigation workflow state (design section 2.8).

The state is a Pydantic model so it can be validated, persisted as JSON into
``investigation_runs.state``, and reloaded for checkpoint recovery. Agent
outputs are stored keyed by agent name for idempotent re-runs.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class InvestigationStatus(str, Enum):
    CREATED = "created"
    VALIDATING = "validating"
    HASHING = "hashing"
    PLANNING = "planning"
    AGENTS_RUNNING = "agents_running"
    NORMALIZING = "normalizing"
    GRAPHING = "graphing"
    TIMELINE = "timeline"
    DEFENSE = "defense"
    CONFIDENCE = "confidence"
    REPORT_DRAFT = "report_draft"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IndicatorRef(BaseModel):
    evidence_id: str
    indicator_type: str
    value: str


class FileRef(BaseModel):
    evidence_id: str
    filename: str
    sha256: str | None = None
    mime_type: str | None = None


class StepError(BaseModel):
    node: str
    message: str
    retriable: bool = True


class AgentResult(BaseModel):
    """Normalized output of a single agent run (persisted for idempotency)."""

    agent_name: str
    status: str  # completed | failed | skipped
    findings: list[dict] = Field(default_factory=list)
    source_refs: list[dict] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class ContradictionItem(BaseModel):
    # kind in {verified_contradiction, plausible_alternative, open_question}
    kind: str
    description: str
    basis: str | None = None
    refs: dict = Field(default_factory=dict)


class ConfidenceResult(BaseModel):
    score: float | None = None
    band: str = "insufficient"
    factors: dict[str, dict] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    # Supplementary IBM Z scoring (clearly labelled; may be simulated/unavailable).
    ibmz: dict | None = None


class InvestigationState(BaseModel):
    """Full workflow state carried between nodes and persisted per run."""

    investigation_id: str
    case_id: str
    started_by: str
    status: InvestigationStatus = InvestigationStatus.CREATED

    indicators: list[IndicatorRef] = Field(default_factory=list)
    files: list[FileRef] = Field(default_factory=list)

    # Agent results keyed by agent name (idempotency key).
    agent_results: dict[str, AgentResult] = Field(default_factory=dict)

    findings: list[dict] = Field(default_factory=list)
    hypothesis: str | None = None
    contradictions: list[ContradictionItem] = Field(default_factory=list)
    confidence: ConfidenceResult | None = None
    timeline: list[dict] = Field(default_factory=list)
    graph_summary: dict = Field(default_factory=dict)

    errors: list[StepError] = Field(default_factory=list)
    defense_rounds: int = 0
    cancel_requested: bool = False

    def to_json(self) -> dict:
        return self.model_dump(mode="json")

    @classmethod
    def from_json(cls, data: dict) -> InvestigationState:
        return cls.model_validate(data)
