"""Evidence endpoints: upload files, submit indicators, verify, extract metadata.

File uploads are read into memory up to the configured cap, validated (MIME +
magic bytes + zip-bomb guard), hashed, and stored. Oversized bodies are rejected
before full processing where possible.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.deps import CaseContext, require_case_member
from app.api.schemas import (
    EvidenceResponse,
    IndicatorSubmit,
    MetadataResponse,
    VerifyResponse,
)
from app.config import get_settings
from app.domain.errors import ValidationError
from app.persistence.postgres.database import get_db_session
from app.services.evidence_service import EvidenceService
from sqlalchemy.ext.asyncio import AsyncSession

# Case-scoped evidence routes. Keeping case_id in the path lets the
# require_case_member dependency enforce authorization uniformly.
router = APIRouter(prefix="/cases/{case_id}/evidence", tags=["evidence"])


@router.post("", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    case_id: uuid.UUID,
    file: UploadFile = File(...),
    ctx: CaseContext = Depends(require_case_member(write=True)),
    session: AsyncSession = Depends(get_db_session),
) -> EvidenceResponse:
    """Upload a file as evidence."""
    settings = get_settings()
    # Read with a hard cap: read one extra byte to detect oversize without
    # buffering unbounded input.
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise ValidationError(
            f"File exceeds max size ({settings.max_upload_bytes} bytes)"
        )

    service = EvidenceService(session)
    evidence = await service.upload_file(
        case_id=case_id,
        data=data,
        filename=file.filename or "upload.bin",
        declared_mime=file.content_type or "application/octet-stream",
        actor_id=ctx.user.id,
    )
    return EvidenceResponse.model_validate(evidence)


@router.post("/indicator", response_model=EvidenceResponse, status_code=201)
async def submit_indicator(
    case_id: uuid.UUID,
    body: IndicatorSubmit,
    ctx: CaseContext = Depends(require_case_member(write=True)),
    session: AsyncSession = Depends(get_db_session),
) -> EvidenceResponse:
    """Submit an indicator (username/email/domain/ip/wallet/tx_hash) as evidence."""
    service = EvidenceService(session)
    evidence = await service.submit_indicator(
        case_id=case_id,
        indicator_type=body.indicator_type,
        value=body.value,
        source=body.source,
        actor_id=ctx.user.id,
    )
    return EvidenceResponse.model_validate(evidence)


@router.get("", response_model=list[EvidenceResponse])
async def list_evidence(
    case_id: uuid.UUID,
    ctx: CaseContext = Depends(require_case_member()),
    session: AsyncSession = Depends(get_db_session),
) -> list[EvidenceResponse]:
    service = EvidenceService(session)
    items = await service.list_evidence(case_id)
    return [EvidenceResponse.model_validate(i) for i in items]


@router.get("/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(
    case_id: uuid.UUID,
    evidence_id: uuid.UUID,
    ctx: CaseContext = Depends(require_case_member()),
    session: AsyncSession = Depends(get_db_session),
) -> EvidenceResponse:
    service = EvidenceService(session)
    evidence = await service.get_evidence(evidence_id, case_id)
    return EvidenceResponse.model_validate(evidence)


@router.post("/{evidence_id}/metadata", response_model=MetadataResponse)
async def extract_metadata(
    case_id: uuid.UUID,
    evidence_id: uuid.UUID,
    ctx: CaseContext = Depends(require_case_member(write=True)),
    session: AsyncSession = Depends(get_db_session),
) -> MetadataResponse:
    service = EvidenceService(session)
    evidence = await service.get_evidence(evidence_id, case_id)
    result = await service.extract_file_metadata(evidence=evidence, actor_id=ctx.user.id)
    return MetadataResponse(**result)


@router.post("/{evidence_id}/verify", response_model=VerifyResponse)
async def verify_evidence(
    case_id: uuid.UUID,
    evidence_id: uuid.UUID,
    ctx: CaseContext = Depends(require_case_member()),
    session: AsyncSession = Depends(get_db_session),
) -> VerifyResponse:
    service = EvidenceService(session)
    evidence = await service.get_evidence(evidence_id, case_id)
    result = await service.verify_integrity(evidence=evidence, actor_id=ctx.user.id)
    return VerifyResponse(**result)
