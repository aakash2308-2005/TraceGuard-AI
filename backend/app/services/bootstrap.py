"""Idempotent bootstrap: ensure roles and an initial admin user exist.

Reads the initial admin credentials from the environment. Safe to run on every
startup; it only creates what is missing.
"""

import os

from sqlalchemy import select

from app.observability.logging import get_logger
from app.persistence.postgres.database import get_sessionmaker
from app.persistence.postgres.models import User
from app.services.admin_service import AdminService

logger = get_logger("bootstrap")


async def bootstrap_roles_and_admin() -> None:
    """Create roles and a default admin if absent."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        admin_service = AdminService(session)
        await admin_service.ensure_roles()

        admin_username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "admin")
        result = await session.execute(select(User).where(User.username == admin_username))
        admin = result.scalar_one_or_none()
        if admin is None:
            password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "ChangeMe123!")
            email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "admin@traceguard.local")
            await admin_service.create_user(
                username=admin_username,
                email=email,
                password=password,
                role="admin",
            )
            logger.info("bootstrap_admin_created", username=admin_username)
            refreshed = await session.execute(select(User).where(User.username == admin_username))
            admin = refreshed.scalar_one_or_none()
        if admin is not None and admin.full_name is None:
            # Reports sign their "Name" line from here — idempotent backfill.
            admin.full_name = os.environ.get("BOOTSTRAP_ADMIN_NAME", "Administrator")
            logger.info("bootstrap_admin_name_set", username=admin_username)
        await session.commit()
