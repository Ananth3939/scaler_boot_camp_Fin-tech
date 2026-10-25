from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from finsight.agents.financial_data import compute_key_ratios
from finsight.agents.news_sentiment import assess_headline_sentiment
from finsight.agents.report_writer import write_markdown_report
from finsight.agents.risk import assess_risk
from finsight.agents.valuation import calculate_dcf
from finsight.config import Settings, get_settings
from finsight.llm.factory import create_llm_provider
from finsight.models import (
    AgentResult,
    CompanyProfile,
    DataSource,
    FinancialStatements,
    ModelSummary,
    NewsSearchResult,
    NewsSentimentAssessment,
    PriceHistory,
    RatioReport,
    ResearchResponse,
    RiskAssessment,
    StockPrice,
    ValuationResult,
)
from finsight.services import create_market_data_service, create_news_service
from finsight.tools.market_data import normalize_ticker


def run_research(
    ticker: str,
    settings: Settings | None = None,
    *,
    include_news: bool = True,
    include_valuation: bool = True,
) -> ResearchResponse:
    """Run independent data fetches concurrently, then assemble typed analysis results."""
    settings = settings or get_settings()
    normalized = normalize_ticker(ticker)
    market = create_market_data_service(settings)
    news_service = create_news_service(settings)

    operations = {
        "price": lambda: market.get_stock_price(normalized),
        "history": lambda: market.get_price_history(normalized),
        "company": lambda: market.get_company_info(normalized),
        "statements": lambda: market.get_financial_statements(normalized),
    }
    if include_news:
        operations["news"] = lambda: news_service.search_recent_news(normalized, limit=10)
    executor = ThreadPoolExecutor(max_workers=min(settings.max_concurrent_agents, len(operations)))
    futures: dict[str, Future[Any]] = {
        name: executor.submit(operation) for name, operation in operations.items()
    }
    done, _ = wait(
        futures.values(),
        timeout=max(settings.request_timeout_seconds * 4, 30),
    )
    completed = set(done)
    results: dict[str, Any] = {}
    failures: dict[str, str] = {}
    for name, future in futures.items():
        if future in completed:
            try:
                results[name] = future.result()
            except Exception as exc:
                failures[name] = _error_text(exc)
        else:
            future.cancel()
            failures[name] = "workflow deadline exceeded"
    executor.shutdown(wait=False, cancel_futures=True)

    price = _as_type(results.get("price"), StockPrice)
    price_history = _as_type(results.get("history"), PriceHistory)
    company = _as_type(results.get("company"), CompanyProfile)
    statements = _as_type(results.get("statements"), FinancialStatements)
    news = _as_type(results.get("news"), NewsSearchResult)
    ratios = compute_key_ratios(statements) if statements is not None else None
    sentiment = assess_headline_sentiment(news) if include_news else _not_requested_sentiment()
    risk = assess_risk(ratios, price_history)
    valuation = (
        calculate_dcf(statements, company)
        if include_valuation
        else ValuationResult(
            status="not_requested",
            summary="Valuation was not requested.",
        )
    )
    try:
        model_summary = create_llm_provider(settings).summarize(
            _summary_context(normalized, price, ratios, risk, valuation, news)
        )
    except Exception as exc:
        model_summary = ModelSummary(
            provider=settings.llm_provider,
            status="failed",
            warnings=[f"Summary provider could not run ({type(exc).__name__})."],
        )

    warnings = [f"{name} data unavailable: {detail}" for name, detail in failures.items()]
    if include_news and sentiment.status != "success":
        warnings.append("News sentiment is a partial headline-only keyword screen.")
    if risk.status != "success":
        warnings.append("Risk coverage is partial; see the risk findings and coverage limits.")
    if include_valuation and valuation.status != "success":
        warnings.append(f"Valuation status: {valuation.status}; see its assumptions and caveats.")
    if model_summary.status != "success":
        warnings.extend(model_summary.warnings or ["Model summary was unavailable."])
    if price is None and company is None and statements is None and news is None:
        status: Literal["success", "partial", "failed"] = "failed"
    elif (
        failures
        or risk.status != "success"
        or (include_valuation and valuation.status != "success")
        or (include_news and sentiment.status != "success")
        or model_summary.status != "success"
    ):
        status = "partial"
    else:
        status = "success"

    agents = _agent_results(
        statements=statements,
        ratios=ratios,
        news=news,
        sentiment_summary=sentiment.summary,
        sentiment_warnings=sentiment.warnings,
        risk=risk,
        price_history=price_history,
        valuation=valuation,
        failures=failures,
        include_news=include_news,
        include_valuation=include_valuation,
        model_summary=model_summary,
    )
    markdown = write_markdown_report(
        ticker=normalized,
        company=company,
        price=price,
        ratios=ratios,
        news=news,
        sentiment=sentiment,
        risk=risk,
        valuation=valuation,
        warnings=warnings,
        model_summary=model_summary,
    )
    return ResearchResponse(
        request_id=str(uuid4()),
        ticker=normalized,
        status=status,
        generated_at=datetime.now(UTC),
        company=company,
        stock_price=price,
        financial_statements=statements,
        ratios=ratios,
        news=news,
        news_sentiment=sentiment,
        risk=risk,
        valuation=valuation,
        model_summary=model_summary,
        agents=agents,
        warnings=warnings,
        markdown_report=markdown,
    )


def _agent_results(
    *,
    statements: FinancialStatements | None,
    ratios: RatioReport | None,
    news: NewsSearchResult | None,
    sentiment_summary: str,
    sentiment_warnings: list[str],
    risk: RiskAssessment,
    price_history: PriceHistory | None,
    valuation: ValuationResult,
    failures: dict[str, str],
    include_news: bool,
    include_valuation: bool,
    model_summary: ModelSummary,
) -> list[AgentResult]:
    financial_warnings = list(failures.values()) if "statements" in failures else []
    if statements:
        financial_warnings.extend(statements.warnings)
    financial_status: Literal["success", "partial", "failed"] = (
        "failed" if statements is None else "partial" if financial_warnings else "success"
    )
    news_warnings = list(sentiment_warnings)
    if news:
        news_warnings.extend(news.warnings)
    if "news" in failures:
        news_warnings.append(failures["news"])
    news_status: Literal["success", "partial", "failed"] = (
        "partial"
        if not include_news
        else "failed"
        if news is None
        else "partial"
        if news_warnings or not news.articles
        else "success"
    )
    valuation_status: Literal["success", "partial", "failed"] = (
        "failed"
        if valuation.status == "failed"
        else "partial"
        if valuation.status != "success"
        else "success"
    )

    return [
        AgentResult(
            agent_name="Financial Data Agent",
            status=financial_status,
            summary=(
                f"Retrieved {len(statements.income_statement)} income, "
                f"{len(statements.balance_sheet)} balance sheet, and "
                f"{len(statements.cash_flow)} cash flow periods."
                if statements
                else "Financial statements were unavailable."
            ),
            findings=[f"Calculated ratios: {', '.join(ratios.values) or 'none'}."]
            if ratios
            else [],
            sources=[statements.source] if statements else [],
            warnings=financial_warnings,
        ),
        AgentResult(
            agent_name="News & Sentiment Agent",
            status=news_status,
            summary=sentiment_summary if include_news else "News retrieval was not requested.",
            findings=[f"Retrieved {len(news.articles)} headline(s)."] if news else [],
            sources=[news.source] if news else [],
            warnings=news_warnings,
        ),
        AgentResult(
            agent_name="Risk Agent",
            status=risk.status,
            summary=risk.summary,
            findings=[
                f"{finding.metric_name}: {finding.value:.2f} {finding.unit} ({finding.severity})."
                for finding in risk.findings
            ],
            sources=[price_history.source] if price_history else [],
            warnings=risk.warnings,
        ),
        AgentResult(
            agent_name="Valuation Agent",
            status=valuation_status,
            summary=valuation.summary,
            findings=(
                [
                    "Estimated value per share: "
                    f"{valuation.currency} {valuation.estimated_value_per_share:.2f}."
                ]
                if valuation.estimated_value_per_share is not None
                else []
            ),
            warnings=valuation.warnings,
        ),
        AgentResult(
            agent_name="Report Writer Agent",
            status=(
                "partial"
                if failures
                or valuation.status in {"unavailable", "not_requested"}
                or model_summary.status != "success"
                else "success"
            ),
            summary="Assembled a source-aware Markdown brief from the available tool results.",
            sources=_unique_sources(statements, news, ratios),
            warnings=list(failures.values()) + model_summary.warnings,
        ),
    ]


def _unique_sources(
    statements: FinancialStatements | None,
    news: NewsSearchResult | None,
    ratios: RatioReport | None,
) -> list[DataSource]:
    sources: list[DataSource] = []
    seen: set[tuple[str, str | None]] = set()
    candidates = [
        statements.source if statements else None,
        news.source if news else None,
        ratios.source if ratios else None,
    ]
    for source in candidates:
        if source is None:
            continue
        key = (source.provider, source.url)
        if key not in seen:
            sources.append(source)
            seen.add(key)
    return sources


def _as_type(value: Any, expected: type[Any]) -> Any:
    return value if isinstance(value, expected) else None


def _error_text(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    return text[:240] if text else type(exc).__name__


def _not_requested_sentiment() -> NewsSentimentAssessment:
    return NewsSentimentAssessment(
        status="success",
        method="not requested",
        positive_headlines=0,
        negative_headlines=0,
        neutral_headlines=0,
        summary="News analysis was not requested.",
    )


def _summary_context(
    ticker: str,
    price: StockPrice | None,
    ratios: RatioReport | None,
    risk: RiskAssessment,
    valuation: ValuationResult,
    news: NewsSearchResult | None,
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "stock_price": (
            {
                "close": price.close,
                "currency": price.currency,
                "as_of": price.as_of.isoformat(),
            }
            if price
            else None
        ),
        "ratios": {key: metric.value for key, metric in ratios.values.items()} if ratios else {},
        "risk_findings": [
            f"{finding.severity} {finding.metric_name}: {finding.value:.2f} {finding.unit}"
            for finding in risk.findings
        ],
        "valuation": {
            "status": valuation.status,
            "estimated_value_per_share": valuation.estimated_value_per_share,
            "currency": valuation.currency,
            "assumptions": valuation.assumptions,
            "summary": valuation.summary,
        },
        "news_headlines": [article.title[:300] for article in news.articles[:10]] if news else [],
    }
