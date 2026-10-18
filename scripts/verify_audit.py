"""Verify the audit log hash-chain integrity.

Run from the backend directory (needs the app package + DB access):

    python ../scripts/verify_audit.py

Exits 0 if the chain is intact, 1 if a break is detected.
"""

import asyncio
import sys


async def _main() -> int:
    try:
        from app.persistence.postgres.database import get_sessionmaker
        from app.services.audit_service import AuditService
    except ImportError:
        print("Run this from the backend/ directory so the app package is importable.")
        return 2

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await AuditService(session).verify_chain()
    if result.get("valid"):
        print(f"Audit chain intact. Entries: {result.get('count')}")
        return 0
    print(f"AUDIT CHAIN BROKEN at index {result.get('broken_at')} "
          f"(event {result.get('event_id')})")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
