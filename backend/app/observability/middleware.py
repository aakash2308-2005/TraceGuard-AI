"""ASGI middleware that assigns a correlation ID and records request metrics."""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.observability.logging import correlation_id_var, get_logger
from app.observability.metrics import REQUEST_LATENCY

logger = get_logger("http")


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Assign/propagate a correlation ID and emit structured access logs."""

    async def dispatch(self, request: Request, call_next) -> Response:
        cid = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        token = correlation_id_var.set(cid)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["x-correlation-id"] = cid
            return response
        finally:
            elapsed = time.perf_counter() - start
            path = request.url.path
            REQUEST_LATENCY.labels(request.method, path, str(status_code)).observe(elapsed)
            logger.info(
                "request",
                method=request.method,
                path=path,
                status=status_code,
                duration_ms=round(elapsed * 1000, 2),
            )
            correlation_id_var.reset(token)
