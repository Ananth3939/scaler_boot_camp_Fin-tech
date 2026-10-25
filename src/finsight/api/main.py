from __future__ import annotations

import uvicorn
from fastapi import FastAPI, HTTPException

from finsight import __version__
from finsight.api.schemas import HealthResponse, ResearchRequest
from finsight.api.store import ResearchStore
from finsight.config import get_settings
from finsight.models import ResearchResponse
from finsight.orchestration.workflow import run_research

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "Local financial research API. Results are educational research outputs, "
        "not investment advice."
    ),
)
research_store = ResearchStore(ttl_seconds=settings.cache_ttl_seconds)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(app_name=settings.app_name, version=__version__)


@app.post("/research", response_model=ResearchResponse, tags=["research"])
def create_research(request: ResearchRequest) -> ResearchResponse:
    result = run_research(
        request.ticker,
        settings,
        include_news=request.include_news,
        include_valuation=request.include_valuation,
    )
    research_store.put(result)
    return result


@app.get("/research/{request_id}", response_model=ResearchResponse, tags=["research"])
def get_research(request_id: str) -> ResearchResponse:
    result = research_store.get(request_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail="Research request was not found or has expired."
        )
    return result


def run() -> None:
    """Start the API on loopback by default; configure a secure deployment separately."""
    uvicorn.run(
        "finsight.api.main:app", host=settings.api_host, port=settings.api_port, reload=False
    )
