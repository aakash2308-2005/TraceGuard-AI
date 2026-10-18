"""Seed synthetic demo data.

Creates demo users and roles. Full synthetic investigation scenarios are added
in M10. Idempotent: safe to run multiple times.

Usage:
    python -m app.cli seed
"""

import asyncio

from sqlalchemy import select

from app.observability.logging import get_logger
from app.persistence.postgres.database import get_sessionmaker
from app.persistence.postgres.models import User
from app.services.admin_service import AdminService

logger = get_logger("seed")

_DEMO_USERS = [
    ("lead", "lead@traceguard.local", "LeadPass123!", "lead_investigator"),
    ("analyst", "analyst@traceguard.local", "AnalystPass123!", "investigator"),
    ("reviewer", "reviewer@traceguard.local", "ReviewPass123!", "reviewer"),
]


async def _seed() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        admin = AdminService(session)
        await admin.ensure_roles()
        for username, email, password, role in _DEMO_USERS:
            exists = await session.execute(select(User).where(User.username == username))
            if exists.scalar_one_or_none() is None:
                await admin.create_user(
                    username=username, email=email, password=password, role=role
                )
                logger.info("seed_user_created", username=username)
        await session.commit()

        await _seed_demo_case(session)
        await session.commit()


async def _seed_demo_case(session) -> None:
    """Create a demo case seeded with the coincidental shared-IP scenario (S2).

    This scenario is the showcase for the Defense Agent: it should flag the
    shared IP as a plausible alternative explanation (a false lead), not a link.
    Idempotent: skipped if the demo case already exists.
    """
    from app.services.case_service import CaseService
    from app.services.evidence_service import EvidenceService

    lead = await session.execute(select(User).where(User.username == "lead"))
    lead_user = lead.scalar_one_or_none()
    if lead_user is None:
        return

    from app.persistence.postgres.models import Case

    existing = await session.execute(select(Case).where(Case.title == "Demo: Shared-IP False Lead"))
    if existing.scalar_one_or_none() is not None:
        return

    case_service = CaseService(session)
    case = await case_service.create_case(
        title="Demo: Shared-IP False Lead",
        description="Synthetic scenario S2. Two unrelated indicators share one VPN exit IP.",
        creator_id=lead_user.id,
    )
    await session.flush()

    evidence_service = EvidenceService(session)
    for itype, value in [
        ("ip", "198.51.100.23"),
        ("domain", "unrelated-blog.example.org"),
        ("username", "unrelated_user"),
    ]:
        await evidence_service.submit_indicator(
            case_id=case.id,
            indicator_type=itype,
            value=value,
            source="synthetic_seed",
            actor_id=lead_user.id,
        )
    logger.info("seed_demo_case_created", case_id=str(case.id))


def run_seed() -> None:
    """Synchronous entrypoint used by app.cli."""
    asyncio.run(_seed())


if __name__ == "__main__":
    run_seed()
