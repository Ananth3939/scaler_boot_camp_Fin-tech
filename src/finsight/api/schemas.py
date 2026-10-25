from typing import Literal

from finsight.models import FinSightModel, Ticker


class ResearchRequest(FinSightModel):
    ticker: Ticker
    include_news: bool = True
    include_valuation: bool = True


class HealthResponse(FinSightModel):
    status: Literal["ok"] = "ok"
    app_name: str
    version: str
