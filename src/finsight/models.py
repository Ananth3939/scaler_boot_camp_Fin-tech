from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Ticker = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        pattern=r"^[A-Z0-9][A-Z0-9.-]{0,14}$",
    ),
]


def utc_now() -> datetime:
    return datetime.now(UTC)


class FinSightModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataSource(FinSightModel):
    provider: str
    url: str | None = None
    retrieved_at: datetime = Field(default_factory=utc_now)


class StockPrice(FinSightModel):
    ticker: Ticker
    close: float = Field(ge=0)
    currency: str | None = None
    as_of: date
    source: DataSource


class PricePoint(FinSightModel):
    as_of: date
    close: float = Field(gt=0)


class PriceHistory(FinSightModel):
    ticker: Ticker
    currency: str | None = None
    points: list[PricePoint]
    source: DataSource


class CompanyProfile(FinSightModel):
    ticker: Ticker
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    exchange: str | None = None
    country: str | None = None
    currency: str | None = None
    website: str | None = None
    description: str | None = None
    market_cap: float | None = Field(default=None, ge=0)
    employees: int | None = Field(default=None, ge=0)
    shares_outstanding: float | None = Field(default=None, gt=0)
    source: DataSource


class StatementPeriod(FinSightModel):
    period_end: date
    # Provider line-item names are retained so that the source data remains auditable.
    values: dict[str, float | None]


class FinancialStatements(FinSightModel):
    ticker: Ticker
    income_statement: list[StatementPeriod]
    balance_sheet: list[StatementPeriod]
    cash_flow: list[StatementPeriod]
    currency: str | None = None
    source: DataSource
    warnings: list[str] = Field(default_factory=list)


class RatioValue(FinSightModel):
    value: float
    unit: Literal["percent", "ratio"]
    formula: str
    period_end: date | None = None


class RatioReport(FinSightModel):
    ticker: Ticker
    values: dict[str, RatioValue]
    source: DataSource
    warnings: list[str] = Field(default_factory=list)


class NewsArticle(FinSightModel):
    title: str
    publisher: str | None = None
    published_at: datetime | None = None
    url: str | None = None


class NewsSearchResult(FinSightModel):
    ticker: Ticker
    articles: list[NewsArticle]
    source: DataSource
    warnings: list[str] = Field(default_factory=list)


class AgentResult(FinSightModel):
    agent_name: str
    status: Literal["success", "partial", "failed"]
    summary: str
    findings: list[str] = Field(default_factory=list)
    sources: list[DataSource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class NewsSentimentAssessment(FinSightModel):
    status: Literal["success", "partial", "failed"]
    method: str
    positive_headlines: int = Field(ge=0)
    negative_headlines: int = Field(ge=0)
    neutral_headlines: int = Field(ge=0)
    summary: str
    warnings: list[str] = Field(default_factory=list)


class RiskFinding(FinSightModel):
    severity: Literal["informational", "moderate", "high"]
    metric_name: str
    value: float
    unit: str
    threshold: str
    explanation: str
    period_start: date | None = None
    period_end: date | None = None


class RiskAssessment(FinSightModel):
    status: Literal["success", "partial", "failed"]
    findings: list[RiskFinding]
    summary: str
    warnings: list[str] = Field(default_factory=list)


class ValuationSensitivity(FinSightModel):
    growth_rate: float = Field(ge=0, le=0.5)
    discount_rate: float = Field(gt=0, lt=1)
    estimated_value_per_share: float


class ValuationResult(FinSightModel):
    status: Literal["success", "partial", "unavailable", "not_requested", "failed"]
    method: str = "Illustrative discounted cash flow"
    estimated_value_per_share: float | None = None
    currency: str | None = None
    assumptions: dict[str, float] = Field(default_factory=dict)
    sensitivity: list[ValuationSensitivity] = Field(default_factory=list)
    summary: str
    warnings: list[str] = Field(default_factory=list)


class ModelSummary(FinSightModel):
    provider: str
    model_id: str | None = None
    status: Literal["success", "unavailable", "failed"]
    summary: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    latency_ms: float | None = Field(default=None, ge=0)
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class ResearchResponse(FinSightModel):
    request_id: str
    ticker: Ticker
    status: Literal["success", "partial", "failed"]
    generated_at: datetime = Field(default_factory=utc_now)
    company: CompanyProfile | None = None
    stock_price: StockPrice | None = None
    financial_statements: FinancialStatements | None = None
    ratios: RatioReport | None = None
    news: NewsSearchResult | None = None
    news_sentiment: NewsSentimentAssessment
    risk: RiskAssessment
    valuation: ValuationResult
    model_summary: ModelSummary
    agents: list[AgentResult]
    warnings: list[str] = Field(default_factory=list)
    markdown_report: str
