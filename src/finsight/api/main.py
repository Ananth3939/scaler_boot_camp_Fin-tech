from __future__ import annotations

import hmac
import ipaddress
import json
import logging
from collections.abc import Callable
from time import perf_counter
from uuid import uuid4

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import RequestResponseEndpoint

from finsight import __version__
from finsight.api.schemas import HealthResponse, ResearchRequest
from finsight.api.security import InMemoryRateLimiter
from finsight.api.store import ResearchStore
from finsight.config import Settings, get_settings
from finsight.models import ResearchResponse
from finsight.orchestration.workflow import run_research

logger = logging.getLogger("finsight.api")
ResearchRunner = Callable[..., ResearchResponse]
bearer_auth = HTTPBearer(auto_error=False)


def create_app(
    settings: Settings | None = None,
    *,
    researcher: ResearchRunner | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    research_runner = researcher or run_research
    research_store = ResearchStore(ttl_seconds=resolved_settings.cache_ttl_seconds)
    rate_limiter = InMemoryRateLimiter(
        resolved_settings.rate_limit_requests,
        resolved_settings.rate_limit_window_seconds,
    )
    application = FastAPI(
        title=resolved_settings.app_name,
        version=__version__,
        description=(
            "Local financial research API. Research routes support optional bearer authentication "
            "and a bounded per-process rate limit. This is not investment advice."
        ),
    )

    @application.middleware("http")
    async def log_requests(request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = uuid4().hex
        start = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = correlation_id
            return response
        finally:
            route = request.scope.get("route")
            route_path = getattr(route, "path", request.url.path)
            logger.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": correlation_id,
                        "method": request.method,
                        "route": route_path,
                        "status_code": status_code,
                        "duration_ms": round((perf_counter() - start) * 1000, 2),
                    },
                    separators=(",", ":"),
                )
            )

    def require_access(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_auth),  # noqa: B008
    ) -> None:
        client_key = request.client.host if request.client else "unknown"
        retry_after = rate_limiter.retry_after(client_key)
        if retry_after is not None:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Retry after the indicated delay.",
                headers={"Retry-After": str(retry_after)},
            )

        expected_key = resolved_settings.api_key.get_secret_value()
        if expected_key:
            supplied_key = credentials.credentials if credentials else ""
            if not hmac.compare_digest(expected_key.encode("utf-8"), supplied_key.encode("utf-8")):
                raise HTTPException(
                    status_code=401,
                    detail="A valid bearer API key is required.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    application.state.research_store = research_store

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(app_name=resolved_settings.app_name, version=__version__)

    @application.post(
        "/research",
        response_model=ResearchResponse,
        tags=["research"],
        dependencies=[Depends(require_access)],
    )
    def create_research(request: ResearchRequest) -> ResearchResponse:
        result = research_runner(
            request.ticker,
            resolved_settings,
            include_news=request.include_news,
            include_valuation=request.include_valuation,
            peer_tickers=request.peer_tickers,
        )
        research_store.put(result)
        return result

    @application.get(
        "/research/{request_id}",
        response_model=ResearchResponse,
        tags=["research"],
        dependencies=[Depends(require_access)],
    )
    def get_research(request_id: str) -> ResearchResponse:
        result = research_store.get(request_id)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Research request was not found or has expired.",
            )
        return result

    return application


app = create_app()


def _is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def run() -> None:
    """Start the API; non-loopback binds require an API key."""
    settings = get_settings()
    if not _is_loopback_host(settings.api_host) and not settings.api_key.get_secret_value():
        raise RuntimeError("Set API_KEY before binding the API to a non-loopback host.")
    uvicorn.run(
        create_app(settings),
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
