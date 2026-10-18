"""Pydantic request/response schemas for the REST API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# --- Auth ---
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    name: str | None = None
    role: str
    permissions: dict[str, bool]


# --- Cases ---
class CaseCreate(BaseModel):
    case_identifier: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    case_role: str = Field(default="lead", min_length=1, max_length=30)


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, max_length=30)


class CaseResponse(BaseModel):
    id: uuid.UUID
    case_identifier: str
    title: str
    description: str | None
    status: str
    created_by: uuid.UUID
    created_at: datetime
    archived_at: datetime | None
    my_case_role: str | None = None

    model_config = {"from_attributes": True}


class MemberAdd(BaseModel):
    user_id: uuid.UUID
    case_role: str = Field(default="investigator")


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    username: str
    case_role: str


# --- Evidence ---
class IndicatorSubmit(BaseModel):
    indicator_type: str = Field(description="username|email|domain|ip|wallet|tx_hash")
    value: str = Field(min_length=1, max_length=512)
    source: str | None = Field(default=None, max_length=255)


class EvidenceResponse(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    type: str
    indicator_type: str | None
    indicator_value: str | None
    original_filename: str | None
    mime_type: str | None
    size_bytes: int | None
    sha256: str | None
    verification_status: str
    retention_status: str
    source: str | None
    acquired_at: datetime
    processing_history: list
    chain_of_custody: list

    model_config = {"from_attributes": True}


class MetadataResponse(BaseModel):
    metadata: dict
    timestamps: dict
    gps: dict
    limitations: list[str]
    epistemic_status: str


class VerifyResponse(BaseModel):
    evidence_id: str
    match: bool
    recorded_sha256: str
    computed_sha256: str
    verification_status: str


# --- Investigations ---
class InvestigationCreateResponse(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    status: str


class AgentExecutionResponse(BaseModel):
    agent_name: str
    status: str
    duration_ms: int | None
    error: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvestigationStatusResponse(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    status: str
    hypothesis: str | None = None
    findings_count: int = 0
    contradictions_count: int = 0
    confidence_band: str | None = None
    timeline_count: int = 0
    errors: list[dict] = []
    agent_executions: list[AgentExecutionResponse] = []
    started_at: datetime
    completed_at: datetime | None = None


class FindingResponse(BaseModel):
    agent_name: str
    epistemic_status: str
    claim_type: str | None = None
    payload: dict


class ContradictionResponse(BaseModel):
    kind: str
    description: str
    basis: str | None = None
    refs: dict = {}


class ConfidenceResponse(BaseModel):
    score: float | None
    band: str
    factors: dict
    limitations: list[str]
    ibmz: dict | None = None


class TimelineResponse(BaseModel):
    events: list[dict]


# --- Reports ---
class ReportResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    status: str
    content: dict
    content_hash: str | None
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Graph ---
class GraphNode(BaseModel):
    id: str
    label: str
    value: str
    props: dict = {}


class GraphEdge(BaseModel):
    source: str
    target: str
    rel: str
    provenance: dict = {}


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    note: str | None = None


# --- Admin ---
class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    role: str = Field(default="investigator")


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


# --- Audit ---
class AuditEventResponse(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID | None
    actor_id: uuid.UUID | None
    action: str
    detail: dict
    entry_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}
