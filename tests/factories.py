from datetime import UTC, date, datetime

from finsight.models import (
    CompanyProfile,
    ComparableValuation,
    DataSource,
    FinancialStatements,
    ModelSummary,
    NewsSentimentAssessment,
    ResearchResponse,
    RiskAssessment,
    StatementPeriod,
    ValuationResult,
)


def source(ticker: str) -> DataSource:
    return DataSource(
        provider="fixture",
        url=f"https://example.com/quote/{ticker}",
        retrieved_at=datetime(2026, 1, 2, tzinfo=UTC),
    )


def statements(
    ticker: str,
    *,
    revenue: float | None = 1000,
    net_income: float | None = 100,
    gross_profit: float | None = 400,
    cash: float = 50,
    debt: float = 20,
    fcf: float = 100,
) -> FinancialStatements:
    income_values = {
        "Total Revenue": revenue,
        "Gross Profit": gross_profit,
        "Operating Income": 200.0,
        "Net Income": net_income,
    }
    return FinancialStatements(
        ticker=ticker,
        income_statement=[StatementPeriod(period_end=date(2025, 12, 31), values=income_values)],
        balance_sheet=[
            StatementPeriod(
                period_end=date(2025, 12, 31),
                values={
                    "Current Assets": 300.0,
                    "Current Liabilities": 150.0,
                    "Total Debt": debt,
                    "Stockholders Equity": 100.0,
                    "Cash And Cash Equivalents": cash,
                },
            )
        ],
        cash_flow=[
            StatementPeriod(
                period_end=date(2025, 12, 31),
                values={"Free Cash Flow": fcf, "Operating Cash Flow": fcf + 10},
            )
        ],
        source=source(ticker),
    )


def company(
    ticker: str,
    *,
    market_cap: float | None = 1000,
    shares: float | None = 10,
    currency: str | None = "USD",
) -> CompanyProfile:
    return CompanyProfile(
        ticker=ticker,
        name=f"{ticker} Incorporated",
        currency=currency,
        market_cap=market_cap,
        shares_outstanding=shares,
        source=source(ticker),
    )


def research_response() -> ResearchResponse:
    return ResearchResponse(
        request_id="test-request",
        ticker="AAPL",
        status="success",
        news_sentiment=NewsSentimentAssessment(
            status="success",
            method="fixture",
            positive_headlines=0,
            negative_headlines=0,
            neutral_headlines=0,
            summary="No fixture headlines.",
        ),
        risk=RiskAssessment(status="success", findings=[], summary="No fixture risks."),
        valuation=ValuationResult(status="not_requested", summary="Not requested."),
        comparables=ComparableValuation(
            status="not_requested",
            summary="Comparable valuation was not requested.",
        ),
        model_summary=ModelSummary(
            provider="mock",
            status="success",
            summary="Fixture summary.",
        ),
        agents=[],
        markdown_report="# Fixture report\n",
    )
