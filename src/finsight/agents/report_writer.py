from __future__ import annotations

import re
from urllib.parse import quote, urlsplit

from finsight.models import (
    CompanyProfile,
    ComparableValuation,
    ModelSummary,
    NewsSearchResult,
    NewsSentimentAssessment,
    RatioReport,
    RiskAssessment,
    StockPrice,
    ValuationResult,
)


def write_markdown_report(
    ticker: str,
    company: CompanyProfile | None,
    price: StockPrice | None,
    ratios: RatioReport | None,
    news: NewsSearchResult | None,
    sentiment: NewsSentimentAssessment,
    risk: RiskAssessment,
    valuation: ValuationResult,
    comparables: ComparableValuation,
    warnings: list[str],
    model_summary: ModelSummary | None = None,
) -> str:
    heading = company.name if company and company.name else ticker
    lines = [
        f"# Financial research brief: {heading} ({ticker})",
        "",
        "For education and research only. This is not investment advice.",
        "",
    ]
    if model_summary:
        lines.extend(["## Research summary", f"_Summary provider: {model_summary.provider}._"])
        lines.append(
            model_summary.summary
            or "A model-generated summary was unavailable; the deterministic brief follows."
        )
        lines.append("")
    lines.append("## Snapshot")
    if price:
        currency = price.currency or "currency unavailable"
        lines.append(
            f"- Latest reported close: {currency} {price.close:,.2f} "
            f"(market date {price.as_of.isoformat()}; retrieved "
            f"{price.source.retrieved_at.isoformat()})."
        )
    else:
        lines.append("- Price data unavailable.")
    if company:
        lines.append(
            f"- Sector / industry: {company.sector or 'unavailable'} / "
            f"{company.industry or 'unavailable'}."
        )
        lines.append(f"- Market capitalization: {_money(company.market_cap, company.currency)}.")
    else:
        lines.append("- Company profile unavailable.")

    lines.extend(["", "## Key ratios"])
    if ratios and ratios.values:
        for name, metric in ratios.values.items():
            value = f"{metric.value:.2f}%" if metric.unit == "percent" else f"{metric.value:.2f}x"
            lines.append(f"- {name.replace('_', ' ').title()}: {value} ({metric.formula}).")
    else:
        lines.append("- No ratios could be calculated from the returned statements.")

    lines.extend(["", "## Risk checks"])
    if risk.findings:
        for finding in risk.findings:
            metric_value = (
                f"{finding.value:.1f}%"
                if finding.unit == "percent"
                else f"{finding.value:.2f} {finding.unit}"
            )
            period = (
                f" ({finding.period_start.isoformat()} to {finding.period_end.isoformat()})"
                if finding.period_start and finding.period_end
                else ""
            )
            lines.append(
                f"- **{finding.severity.title()} — {finding.metric_name}:** "
                f"{metric_value}{period}. {finding.explanation} "
                f"Threshold: {finding.threshold}"
            )
    else:
        lines.append("- No liquidity or leverage metrics were available for threshold checks.")
    for warning in risk.warnings:
        lines.append(f"- Coverage limit: {warning}")

    lines.extend(["", "## Valuation scenario"])
    lines.append(f"- {valuation.summary}")
    if valuation.estimated_value_per_share is not None:
        lines.append(
            "- Assumptions: "
            + ", ".join(
                f"{key.replace('_', ' ')}={value:.1%}"
                for key, value in valuation.assumptions.items()
                if "rate" in key or "growth" in key
            )
            + f", projection years={int(valuation.assumptions.get('projection_years', 0))}."
        )
    if valuation.sensitivity:
        lines.append("- Sensitivity (per share):")
        lines.append("\n  | Growth | Discount rate | Estimate |\n  |---:|---:|---:|")
        lines.extend(
            "  | "
            f"{scenario.growth_rate:.1%} | {scenario.discount_rate:.1%} | "
            f"{valuation.currency or 'currency unavailable'} "
            f"{scenario.estimated_value_per_share:,.2f} |"
            for scenario in valuation.sensitivity
        )
    for warning in valuation.warnings:
        lines.append(f"- Caveat: {warning}")

    lines.extend(["", "## Comparable-company scenario"])
    lines.append(f"- {comparables.summary}")
    if comparables.estimated_value_per_share_ps is not None:
        lines.append(
            f"- P/S scenario: {comparables.currency or 'currency unavailable'} "
            f"{comparables.estimated_value_per_share_ps:,.2f} per share."
        )
    if comparables.estimated_value_per_share_pe is not None:
        lines.append(
            f"- P/E scenario: {comparables.currency or 'currency unavailable'} "
            f"{comparables.estimated_value_per_share_pe:,.2f} per share."
        )
    if comparables.peer_metrics:
        lines.append("- Peer multiples:")
        lines.append("\n  | Ticker | P/S | P/E |\n  |---|---:|---:|")
        for peer_metric in comparables.peer_metrics:
            price_to_earnings = (
                f"{peer_metric.price_to_earnings:.2f}x"
                if peer_metric.price_to_earnings is not None
                else "n/a"
            )
            lines.append(
                f"  | {peer_metric.ticker} | {peer_metric.price_to_sales:.2f}x | "
                f"{price_to_earnings} |"
            )
    for warning in comparables.warnings:
        lines.append(f"- Caveat: {warning}")

    lines.extend(["", "## News"])
    lines.append(f"- {sentiment.summary}")
    for warning in sentiment.warnings:
        lines.append(f"- Caveat: {warning}")
    if news and news.articles:
        for article in news.articles[:5]:
            safe_url = _safe_https_url(article.url)
            if safe_url:
                lines.append(
                    f"- [{_markdown_text(article.title)}]({safe_url}) — "
                    f"{article.publisher or 'publisher unavailable'}."
                )
            else:
                lines.append(
                    f"- {_markdown_text(article.title)} — "
                    f"{article.publisher or 'publisher unavailable'} (URL unavailable)."
                )
    else:
        lines.append("- No article links were returned.")

    lines.extend(["", "## Data warnings"])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- No workflow-level warnings.")
    if ratios:
        lines.extend(f"- {warning}" for warning in ratios.warnings)

    sources = []
    for source in [
        price.source if price else None,
        company.source if company else None,
        ratios.source if ratios else None,
        news.source if news else None,
        *comparables.sources,
    ]:
        if source and source.url and source.url not in sources:
            sources.append(source.url)
    lines.extend(["", "## Sources"])
    if sources:
        lines.extend(f"- [{url}]({url})" for url in sources)
    else:
        lines.append("- No sources were available.")
    return "\n".join(lines) + "\n"


def _money(value: float | None, currency: str | None) -> str:
    if value is None:
        return "unavailable"
    return f"{currency or 'currency unavailable'} {value:,.0f}"


def _markdown_text(text: str) -> str:
    # Prevent retrieved headlines from changing the report's Markdown structure.
    flattened = " ".join(text.splitlines())
    return re.sub(r"([\\`*_{}\[\]#!|>])", r"\\\1", flattened)


def _safe_https_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return quote(value, safe=":/?&=#%._~-")
