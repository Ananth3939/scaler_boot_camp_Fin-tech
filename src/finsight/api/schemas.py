from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from finsight.models import FinSightModel, Ticker


class ResearchRequest(FinSightModel):
    ticker: Ticker
    include_news: bool = True
    include_valuation: bool = True
    peer_tickers: list[Ticker] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_peers(self) -> ResearchRequest:
        if self.ticker in self.peer_tickers:
            raise ValueError("the subject ticker cannot also be a peer")
        if len(self.peer_tickers) != len(set(self.peer_tickers)):
            raise ValueError("peer tickers must be unique")
        return self


class HealthResponse(FinSightModel):
    status: Literal["ok"] = "ok"
    app_name: str
    version: str
