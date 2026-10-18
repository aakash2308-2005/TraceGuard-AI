"""Simple management CLI: migrations and seeding.

Usage:
    python -m app.cli migrate
    python -m app.cli seed
"""

import subprocess
import sys

from app.observability.logging import configure_logging, get_logger

logger = get_logger("cli")


def _run_migrations() -> int:
    """Apply Alembic migrations to the latest revision."""
    logger.info("migrate_start")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False,
    )
    if result.returncode == 0:
        logger.info("migrate_complete")
    else:
        logger.error("migrate_failed", returncode=result.returncode)
    return result.returncode


def _run_seed() -> int:
    """Load synthetic seed data (implemented in M2/M10)."""
    try:
        from scripts.seed_data import run_seed  # type: ignore

        run_seed()
        logger.info("seed_complete")
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error("seed_failed", error=str(exc))
        return 1


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python -m app.cli [migrate|seed]")
        return 2
    command = args[0]
    if command == "migrate":
        return _run_migrations()
    if command == "seed":
        return _run_seed()
    print(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
