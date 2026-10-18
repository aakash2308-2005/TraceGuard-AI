"""TraceGuard AI FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from app.api.routes import health
from app.config import get_settings
from app.domain.errors import DomainError
from app.observability.logging import configure_logging, get_logger
from app.observability.middleware import CorrelationMiddleware

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle.

    On startup we configure logging and best-effort ensure object-storage
    buckets exist. We never crash startup because of an optional dependency;
    readiness reports degraded state instead.
    """
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("startup", environment=settings.environment, app=settings.app_name)

    try:
        from app.persistence.objstore.storage import get_object_store

        get_object_store().ensure_buckets()
    except Exception as exc:  # noqa: BLE001
        logger.warning("objstore_init_skipped", error=str(exc))

    try:
        from app.services.bootstrap import bootstrap_roles_and_admin

        await bootstrap_roles_and_admin()
    except Exception as exc:  # noqa: BLE001
        logger.warning("bootstrap_skipped", error=str(exc))

    yield

    try:
        from app.persistence.neo4j.database import close_graph_driver

        await close_graph_driver()
    except Exception as exc:  # noqa: BLE001
        logger.warning("neo4j_shutdown_skipped", error=str(exc))
    logger.info("shutdown")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Agentic AI-powered cybercrime investigation platform.",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def _domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        """Map domain errors to the standard error envelope."""
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    # Health endpoints are unversioned for probe simplicity.
    app.include_router(health.router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/", include_in_schema=False)
    async def root() -> JSONResponse:
        return JSONResponse(
            {
                "name": settings.app_name,
                "tagline": "Connect. Analyze. Uncover.",
                "docs": "/docs",
                "health": "/health",
            }
        )

    # Versioned routers are registered here as later milestones add them.
    _register_v1_routers(app, settings.api_v1_prefix)

    return app


def _register_v1_routers(app: FastAPI, prefix: str) -> None:
    """Register versioned API routers.

    Each import is guarded so the app can boot even while later milestones are
    incomplete. Fully-implemented milestones register unconditionally.
    """
    try:
        from app.api.routes import auth, cases, evidence, investigations, reports, admin, graph

        app.include_router(auth.router, prefix=prefix)
        app.include_router(cases.router, prefix=prefix)
        app.include_router(evidence.router, prefix=prefix)
        app.include_router(investigations.case_router, prefix=prefix)
        app.include_router(investigations.router, prefix=prefix)
        app.include_router(graph.router, prefix=prefix)
        app.include_router(reports.run_router, prefix=prefix)
        app.include_router(reports.router, prefix=prefix)
        app.include_router(admin.router, prefix=prefix)
    except ImportError as exc:  # pragma: no cover - during incremental build
        logger.warning("v1_routers_partial", error=str(exc))


app = create_app()
