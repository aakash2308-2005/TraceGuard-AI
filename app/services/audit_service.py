"""Append-only, hash-chained audit log service (SEC-008, AUD-001/002).

Each entry's hash depends on the previous entry's hash, forming a tamper-evident
chain. Any modification to a historical entry breaks verification downstream.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.logging import get_logger
from app.persistence.postgres.models import AuditEvent

logger = get_logger("audit")

_GENESIS = "0" * 64


def _canonical(payload: dict) -> str:
    """Deterministic JSON serialization for stable hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_entry_hash(prev_hash: str, payload: dict) -> str:
    """Compute entry_hash = sha256(prev_hash || canonical(payload))."""
    material = f"{prev_hash}{_canonical(payload)}".encode()
    return hashlib.sha256(material).hexdigest()


class AuditService:
    """Writes and verifies hash-chained audit events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _latest_hash(self) -> str:
        result = await self._session.execute(
            select(AuditEvent.entry_hash).order_by(desc(AuditEvent.created_at)).limit(1)
        )
        row = result.scalar_one_or_none()
        return row or _GENESIS

    async def record(
        self,
        action: str,
        *,
        actor_id: uuid.UUID | None = None,
        case_id: uuid.UUID | None = None,
        detail: dict | None = None,
    ) -> AuditEvent:
        """Append a new audit event, chaining it to the previous entry."""
        detail = detail or {}
        prev_hash = await self._latest_hash()
        payload = {
            "action": action,
            "actor_id": str(actor_id) if actor_id else None,
            "case_id": str(case_id) if case_id else None,
            "detail": detail,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        entry_hash = compute_entry_hash(prev_hash, payload)
        event = AuditEvent(
            case_id=case_id,
            actor_id=actor_id,
            action=action,
            detail=detail,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
        self._session.add(event)
        await self._session.flush()
        logger.info("audit_event", action=action, actor_id=str(actor_id) if actor_id else None)
        return event

    async def verify_chain(self) -> dict:
        """Recompute the chain and report the first break (if any)."""
        result = await self._session.execute(
            select(AuditEvent).order_by(AuditEvent.created_at)
        )
        events = result.scalars().all()
        prev_hash = _GENESIS
        for idx, event in enumerate(events):
            payload = {
                "action": event.action,
                "actor_id": str(event.actor_id) if event.actor_id else None,
                "case_id": str(event.case_id) if event.case_id else None,
                "detail": event.detail,
                "created_at": event.created_at.isoformat(),
            }
            expected = compute_entry_hash(prev_hash, payload)
            if event.prev_hash != prev_hash or event.entry_hash != expected:
                return {"valid": False, "broken_at": idx, "event_id": str(event.id)}
            prev_hash = event.entry_hash
        return {"valid": True, "count": len(events)}
