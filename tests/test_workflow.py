from __future__ import annotations

from datetime import date

from finsight.config import Settings
from finsight.models import PriceHistory, PricePoint, StockPrice
from finsight.orchestration import workflow
from tests.factories import company, source, statements


class FakeMarketService:
    def get_stock_price(self, ticker: str) -> StockPrice:
        return StockPrice(
            ticker=ticker,
            close=100,
            currency="USD",
            as_of=date(2026, 1, 2),
            source=source(ticker),
        )

    def get_price_history(self, ticker: str) -> PriceHistory:
        return PriceHistory(
            ticker=ticker,
            currency="USD",
            points=[
                PricePoint(as_of=date(2025, 12, 31), close=99),
                PricePoint(as_of=date(2026, 1, 2), close=100),
            ],
            source=source(ticker),
        )

    def get_company_info(self, ticker: str):
        market_caps = {"SUBJ": 500, "PEER1": 120, "PEER2": 200}
        return company(ticker, market_cap=market_caps[ticker], shares=10)

    def get_financial_statements(self, ticker: str):
        financials = {
            "SUBJ": statements(ticker, revenue=50, net_income=5),
            "PEER1": statements(ticker, revenue=60, net_income=6),
            "PEER2": statements(ticker, revenue=100, net_income=10),
        }
        return financials[ticker]


def test_research_workflow_collects_peers_and_writes_comparable_section(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        workflow, "create_market_data_service", lambda _settings: FakeMarketService()
    )
    monkeypatch.setattr(workflow, "create_news_service", lambda _settings: object())

    result = workflow.run_research(
        "SUBJ",
        Settings(llm_provider="mock"),
        include_news=False,
        peer_tickers=["PEER1", "PEER2"],
    )

    assert result.comparables.included_peer_tickers == ["PEER1", "PEER2"]
    assert result.comparables.estimated_value_per_share_ps == 10
    assert "Comparable-company scenario" in result.markdown_report
    assert "PEER1" in result.markdown_report
