"""SQLAlchemy ORM models for TraceGuard AI.

Mirrors the ER design in docs/ARCHITECTURE_AND_DESIGN.md section 2.10. All
tables use UUID primary keys and timezone-aware timestamps. Evidence/findings
use ON DELETE RESTRICT to protect retention; audit events are append-only and
hash-chained (SEC-008).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.postgres.database import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    permissions: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    users: Mapped[list[User]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Optional display name — surfaced on /auth/me and in report headers.
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    role: Mapped[Role] = relationship(back_populates="users")
    memberships: Mapped[list[CaseMembership]] = relationship(back_populates="user")


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = _uuid_pk()
    case_identifier: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = _created_at()
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    memberships: Mapped[list[CaseMembership]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class CaseMembership(Base):
    __tablename__ = "case_memberships"
    __table_args__ = (UniqueConstraint("case_id", "user_id", name="uq_case_user"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_role: Mapped[str] = mapped_column(String(30), default="investigator", nullable=False)
    added_at: Mapped[datetime] = _created_at()

    case: Mapped[Case] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "indicator_type",
            "indicator_value",
            name="uq_case_indicator",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # file | indicator
    indicator_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    indicator_value: Mapped[str | None] = mapped_column(String(512), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    storage_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(20), default="unverified", nullable=False
    )
    retention_status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_retrieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    acquired_at: Mapped[datetime] = _created_at()
    processing_history: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    chain_of_custody: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    access_history: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    derived_artifacts: Mapped[list[DerivedArtifact]] = relationship(
        back_populates="evidence", cascade="all, delete-orphan"
    )


class DerivedArtifact(Base):
    __tablename__ = "derived_artifacts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = _created_at()

    evidence: Mapped[EvidenceItem] = relationship(back_populates="derived_artifacts")


class InvestigationRun(Base):
    __tablename__ = "investigation_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="created", nullable=False, index=True)
    state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    started_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime] = _created_at()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent_executions: Mapped[list[AgentExecution]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    findings: Mapped[list[Finding]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tool_calls: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    error: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = _created_at()

    run: Mapped[InvestigationRun] = relationship(back_populates="agent_executions")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # epistemic_status in {fact, unverified_claim, inference, hypothesis}
    epistemic_status: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    run: Mapped[InvestigationRun] = relationship(back_populates="findings")
    evidence_refs: Mapped[list[EvidenceReference]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )
    source_refs: Mapped[list[ExternalSourceRef]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )


class EvidenceReference(Base):
    __tablename__ = "evidence_references"

    id: Mapped[uuid.UUID] = _uuid_pk()
    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_items.id", ondelete="RESTRICT"), nullable=False
    )
    relation: Mapped[str] = mapped_column(String(50), default="supports", nullable=False)

    finding: Mapped[Finding] = relationship(back_populates="evidence_refs")


class ExternalSourceRef(Base):
    __tablename__ = "external_source_refs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reliability_tier: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)

    finding: Mapped[Finding] = relationship(back_populates="source_refs")


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)
    created_at: Mapped[datetime] = _created_at()

    contradictions: Mapped[list[Contradiction]] = relationship(
        back_populates="hypothesis", cascade="all, delete-orphan"
    )
    confidence_assessments: Mapped[list[ConfidenceAssessment]] = relationship(
        back_populates="hypothesis", cascade="all, delete-orphan"
    )


class Contradiction(Base):
    __tablename__ = "contradictions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # kind in {verified_contradiction, plausible_alternative, open_question}
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    refs: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    hypothesis: Mapped[Hypothesis] = relationship(back_populates="contradictions")


class ConfidenceAssessment(Base):
    __tablename__ = "confidence_assessments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    band: Mapped[str] = mapped_column(String(20), nullable=False)
    factors: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    limitations: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    hypothesis: Mapped[Hypothesis] = relationship(back_populates="confidence_assessments")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    """Append-only, hash-chained audit log (SEC-008, AUD-001/002).

    ``entry_hash = sha256(prev_hash || canonical_json(payload))``. Chain can be
    verified end-to-end by scripts/verify_audit.py.
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = _created_at()
