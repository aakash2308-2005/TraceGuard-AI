"""Evidence processing service (FR-005..008, FR-020).

Pipeline for files: validate -> hash -> store -> record provenance. Indicators
are validated and normalized. Chain-of-custody and processing-history events are
appended to each evidence item and mirrored into the audit log.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain.errors import NotFoundError, ValidationError
from app.domain.indicators import normalize_indicator
from app.observability.logging import get_logger
from app.persistence.objstore.storage import get_object_store
from app.persistence.postgres.models import EvidenceItem
from app.services.audit_service import AuditService
from app.tools.exiftool_runner import extract_metadata
from app.tools.file_validation import validate_file
from app.tools.hasher import sha256_bytes

logger = get_logger("evidence")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _custody_event(action: str, actor_id: uuid.UUID, extra: dict | None = None) -> dict:
    return {
        "action": action,
        "actor_id": str(actor_id),
        "at": _now_iso(),
        **(extra or {}),
    }


class EvidenceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._audit = AuditService(session)

    async def upload_file(
        self,
        *,
        case_id: uuid.UUID,
        data: bytes,
        filename: str,
        declared_mime: str,
        actor_id: uuid.UUID,
    ) -> EvidenceItem:
        """Validate, hash, store, and register a file as evidence."""
        # 1. Validate (raises ValidationError -> 422). Caller treats as rejection.
        validation = validate_file(data=data, declared_mime=declared_mime, filename=filename)

        # 2. Hash for integrity.
        digest = sha256_bytes(data)

        # 3. Store in object storage under a case-scoped key.
        settings = get_settings()
        store = get_object_store()
        key = f"{case_id}/{digest}/{filename}"
        storage_uri = store.put_object(
            settings.s3_bucket_evidence, key, data, validation.mime_type
        )

        # 4. Persist metadata + provenance.
        evidence = EvidenceItem(
            case_id=case_id,
            type="file",
            original_filename=filename,
            mime_type=validation.mime_type,
            size_bytes=validation.size_bytes,
            sha256=digest,
            storage_uri=storage_uri,
            verification_status="verified",  # hash computed at ingest
            uploaded_by=actor_id,
            processing_history=[
                {"step": "validated", "notes": validation.notes, "at": _now_iso()},
                {"step": "hashed", "algo": "sha256", "at": _now_iso()},
                {"step": "stored", "uri": storage_uri, "at": _now_iso()},
            ],
            chain_of_custody=[_custody_event("upload", actor_id, {"sha256": digest})],
        )
        self._session.add(evidence)
        await self._session.flush()

        await self._audit.record(
            "evidence.uploaded",
            actor_id=actor_id,
            case_id=case_id,
            detail={"evidence_id": str(evidence.id), "sha256": digest, "filename": filename},
        )
        logger.info("evidence_uploaded", evidence_id=str(evidence.id), sha256=digest)
        return evidence

    async def submit_indicator(
        self,
        *,
        case_id: uuid.UUID,
        indicator_type: str,
        value: str,
        source: str | None,
        actor_id: uuid.UUID,
    ) -> EvidenceItem:
        """Validate and register an indicator as evidence."""
        normalized = normalize_indicator(indicator_type, value)

        # Enforce per-case uniqueness defensively (DB also constrains it).
        existing = await self._session.execute(
            select(EvidenceItem).where(
                EvidenceItem.case_id == case_id,
                EvidenceItem.indicator_type == indicator_type,
                EvidenceItem.indicator_value == normalized,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValidationError("Indicator already exists in this case")

        evidence = EvidenceItem(
            case_id=case_id,
            type="indicator",
            indicator_type=indicator_type,
            indicator_value=normalized,
            source=source,
            source_retrieved_at=datetime.now(timezone.utc) if source else None,
            verification_status="unverified",
            uploaded_by=actor_id,
            chain_of_custody=[
                _custody_event("submit_indicator", actor_id, {"indicator": normalized})
            ],
        )
        self._session.add(evidence)
        await self._session.flush()

        await self._audit.record(
            "evidence.indicator_submitted",
            actor_id=actor_id,
            case_id=case_id,
            detail={
                "evidence_id": str(evidence.id),
                "indicator_type": indicator_type,
                "value": normalized,
            },
        )
        return evidence

    async def get_evidence(self, evidence_id: uuid.UUID, case_id: uuid.UUID) -> EvidenceItem:
        evidence = await self._session.get(EvidenceItem, evidence_id)
        if evidence is None or evidence.case_id != case_id:
            raise NotFoundError("Evidence not found")
        return evidence

    async def list_evidence(self, case_id: uuid.UUID) -> list[EvidenceItem]:
        result = await self._session.execute(
            select(EvidenceItem)
            .where(EvidenceItem.case_id == case_id)
            .order_by(EvidenceItem.acquired_at.desc())
        )
        return list(result.scalars().all())

    async def extract_file_metadata(
        self, *, evidence: EvidenceItem, actor_id: uuid.UUID
    ) -> dict:
        """Extract EXIF metadata for a stored file (treated as untrusted claims)."""
        if evidence.type != "file" or not evidence.storage_uri:
            raise ValidationError("Metadata extraction only applies to file evidence")

        settings = get_settings()
        store = get_object_store()
        bucket = settings.s3_bucket_evidence
        key = evidence.storage_uri.replace(f"s3://{bucket}/", "", 1)
        data = store.get_object(bucket, key)

        suffix = ""
        if evidence.original_filename and "." in evidence.original_filename:
            suffix = "." + evidence.original_filename.rsplit(".", 1)[1]

        exif = extract_metadata(data, suffix=suffix)

        evidence.processing_history = [
            *evidence.processing_history,
            {
                "step": "metadata_extracted",
                "limitations": exif.limitations,
                "at": _now_iso(),
            },
        ]
        evidence.chain_of_custody = [
            *evidence.chain_of_custody,
            _custody_event("process_metadata", actor_id),
        ]
        await self._session.flush()
        await self._audit.record(
            "evidence.metadata_extracted",
            actor_id=actor_id,
            case_id=evidence.case_id,
            detail={"evidence_id": str(evidence.id)},
        )
        return {
            "metadata": exif.metadata,
            "timestamps": exif.timestamps,
            "gps": exif.gps,
            "limitations": exif.limitations,
            "epistemic_status": "unverified_claim",
        }

    async def verify_integrity(
        self, *, evidence: EvidenceItem, actor_id: uuid.UUID
    ) -> dict:
        """Re-hash stored bytes and compare to the recorded SHA-256 (FR-020)."""
        if evidence.type != "file" or not evidence.storage_uri or not evidence.sha256:
            raise ValidationError("Integrity verification only applies to stored files")

        settings = get_settings()
        store = get_object_store()
        bucket = settings.s3_bucket_evidence
        key = evidence.storage_uri.replace(f"s3://{bucket}/", "", 1)
        data = store.get_object(bucket, key)
        current = sha256_bytes(data)
        match = current == evidence.sha256

        evidence.verification_status = "verified" if match else "mismatch"
        evidence.chain_of_custody = [
            *evidence.chain_of_custody,
            _custody_event("verify", actor_id, {"match": match, "computed": current}),
        ]
        await self._session.flush()
        await self._audit.record(
            "evidence.verified",
            actor_id=actor_id,
            case_id=evidence.case_id,
            detail={"evidence_id": str(evidence.id), "match": match},
        )
        if not match:
            logger.warning(
                "evidence_integrity_mismatch",
                evidence_id=str(evidence.id),
                expected=evidence.sha256,
                computed=current,
            )
        return {
            "evidence_id": str(evidence.id),
            "match": match,
            "recorded_sha256": evidence.sha256,
            "computed_sha256": current,
            "verification_status": evidence.verification_status,
        }
