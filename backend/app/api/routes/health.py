"""Liveness and readiness endpoints (REL-004).

``/health`` is a cheap liveness probe. ``/ready`` checks downstream
dependencies (Postgres, Neo4j, object storage) and reports per-dependency
status without leaking connection details.
"""

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.config import get_settings
from app.observability.logging import get_logger

router = APIRouter(tags=["health"])
logger = get_logger("health")


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str


class ReadyResponse(BaseModel):
    status: str
    dependencies: dict[str, str]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe. Returns 200 as long as the process is serving."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready(response: Response) -> ReadyResponse:
    """Readiness probe. Checks downstream dependencies.

    Each dependency check is isolated so one failure does not mask others.
    Returns 503 if any required dependency is unavailable.
    """
    deps: dict[str, str] = {}

    deps["postgres"] = await _check_postgres()
    deps["neo4j"] = await _check_neo4j()
    deps["object_storage"] = await _check_object_storage()
    # IBM Z is optional; it never fails readiness, but its status is reported.
    deps["ibmz"] = await _check_ibmz()

    # IBM Z does not gate readiness (optional integration).
    required = {k: v for k, v in deps.items() if k != "ibmz"}
    all_ok = all(v == "ok" for v in required.values())
    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(status="ok" if all_ok else "degraded", dependencies=deps)


async def _check_ibmz() -> str:
    """Report IBM Z adapter status (never gates readiness)."""
    try:
        from app.integrations.ibmz.adapter import get_ibmz_adapter

        health = await get_ibmz_adapter().health()
        if health.get("simulated"):
            return "simulated"
        return "ok" if health.get("available") else "unavailable"
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness_check_failed", dependency="ibmz", error=str(exc))
        return "unavailable"


async def _check_postgres() -> str:
    try:
        from sqlalchemy import text

        from app.persistence.postgres.database import get_engine

        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # noqa: BLE001 - readiness must not raise
        logger.warning("readiness_check_failed", dependency="postgres", error=str(exc))
        return "unavailable"


async def _check_neo4j() -> str:
    try:
        from app.persistence.neo4j.database import get_graph_driver

        driver = get_graph_driver()
        await driver.verify_connectivity()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness_check_failed", dependency="neo4j", error=str(exc))
        return "unavailable"


async def _check_object_storage() -> str:
    try:
        from app.persistence.objstore.storage import get_object_store

        store = get_object_store()
        store.healthcheck()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness_check_failed", dependency="object_storage", error=str(exc))
        return "unavailable"
