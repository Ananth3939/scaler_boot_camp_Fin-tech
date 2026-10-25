from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import median
from typing import Literal

from finsight.models import (
    CompanyProfile,
    ComparablePeerMetric,
    ComparableValuation,
    DataSource,
    FinancialStatements,
)
from finsight.tools.market_data import normalize_ticker


def calculate_comparable_valuation(
    company: CompanyProfile | None,
    statements: FinancialStatements | None,
    peers: Sequence[tuple[CompanyProfile | None, FinancialStatements | None]],
    requested_peer_tickers: Sequence[str],
    *,
    peer_errors: Sequence[str] = (),
) -> ComparableValuation:
    """Estimate per-share values from peer P/S and positive-earnings P/E medians."""
    requested = [normalize_ticker(ticker) for ticker in requested_peer_tickers]
    if not requested:
        return ComparableValuation(
            status="not_requested",
            summary="Comparable-company valuation was not requested.",
        )

    warnings = list(peer_errors)
    if company is None or statements is None:
        return ComparableValuation(
            status="unavailable",
            requested_peer_tickers=requested,
            summary="Comparable valuation unavailable because subject-company data were missing.",
            warnings=["Subject-company profile or annual income statement was unavailable."],
        )
    if not company.currency or not company.shares_outstanding:
        missing = []
        if not company.currency:
            missing.append("reporting currency")
        if not company.shares_outstanding:
            missing.append("shares outstanding")
        return ComparableValuation(
            status="unavailable",
            requested_peer_tickers=requested,
            summary=(
                "Comparable valuation unavailable because required subject inputs were missing."
            ),
            warnings=["Missing subject inputs: " + ", ".join(missing) + "."],
        )

    subject_income = statements.income_statement[0] if statements.income_statement else None
    subject_revenue = _line_item(
        subject_income.values if subject_income else None,
        "totalrevenue",
        "operatingrevenue",
        "revenue",
    )
    subject_net_income = _line_item(
        subject_income.values if subject_income else None,
        "netincome",
        "netincomecommonstockholders",
        "netincomecommonstockholdersbasic",
    )
    if subject_revenue is None or subject_revenue <= 0:
        warnings.append("Subject-company annual revenue was unavailable or nonpositive.")
    if subject_net_income is None or subject_net_income <= 0:
        warnings.append("Subject-company annual net income was unavailable or nonpositive.")

    peer_metrics: list[ComparablePeerMetric] = []
    sources: list[DataSource] = [company.source, statements.source]
    for peer_company, peer_statements in peers:
        ticker = (
            peer_company.ticker
            if peer_company
            else peer_statements.ticker
            if peer_statements
            else None
        )
        if peer_company is None or peer_statements is None:
            warnings.append(f"Peer {ticker or 'unknown'} profile or statements were unavailable.")
            continue
        if peer_company.currency != company.currency:
            warnings.append(
                f"Peer {peer_company.ticker} was excluded because its currency "
                f"({peer_company.currency or 'unavailable'}) does not match the subject "
                f"currency ({company.currency})."
            )
            continue
        if peer_company.market_cap is None or peer_company.market_cap <= 0:
            warnings.append(
                f"Peer {peer_company.ticker} was excluded because market cap was missing."
            )
            continue
        period = peer_statements.income_statement[0] if peer_statements.income_statement else None
        if period is None:
            warnings.append(
                f"Peer {peer_company.ticker} was excluded because revenue data were missing."
            )
            continue
        revenue = _line_item(period.values, "totalrevenue", "operatingrevenue", "revenue")
        net_income = _line_item(
            period.values,
            "netincome",
            "netincomecommonstockholders",
            "netincomecommonstockholdersbasic",
        )
        if revenue is None or revenue <= 0:
            warnings.append(
                f"Peer {peer_company.ticker} was excluded because revenue was nonpositive."
            )
            continue
        price_to_sales = peer_company.market_cap / revenue
        price_to_earnings = (
            peer_company.market_cap / net_income
            if net_income is not None and net_income > 0
            else None
        )
        if not math.isfinite(price_to_sales) or (
            price_to_earnings is not None and not math.isfinite(price_to_earnings)
        ):
            warnings.append(
                f"Peer {peer_company.ticker} was excluded because a multiple was invalid."
            )
            continue
        peer_metrics.append(
            ComparablePeerMetric(
                ticker=peer_company.ticker,
                currency=company.currency,
                period_end=period.period_end,
                market_cap=peer_company.market_cap,
                revenue=revenue,
                net_income=net_income,
                price_to_sales=price_to_sales,
                price_to_earnings=price_to_earnings,
            )
        )
        sources.extend([peer_company.source, peer_statements.source])

    if not peer_metrics:
        return ComparableValuation(
            status="unavailable",
            requested_peer_tickers=requested,
            currency=company.currency,
            summary="Comparable valuation unavailable because no usable peers were returned.",
            warnings=warnings or ["No usable peer financial data were returned."],
        )

    sales_multiples = [metric.price_to_sales for metric in peer_metrics]
    earnings_multiples = [
        metric.price_to_earnings for metric in peer_metrics if metric.price_to_earnings is not None
    ]
    median_ps = median(sales_multiples)
    median_pe = median(earnings_multiples) if earnings_multiples else None
    estimated_ps = (
        median_ps * subject_revenue / company.shares_outstanding
        if subject_revenue is not None and subject_revenue > 0
        else None
    )
    estimated_pe = (
        median_pe * subject_net_income / company.shares_outstanding
        if median_pe is not None and subject_net_income is not None and subject_net_income > 0
        else None
    )
    if not earnings_multiples:
        warnings.append("No included peer had positive net income; a P/E estimate was unavailable.")
    warnings.append(
        "The provider does not publish consistent statement-unit metadata. Peer multiples are "
        "calculated from provider values as returned; verify unit comparability before "
        "relying on them."
    )
    if len(peer_metrics) < 3:
        warnings.append(
            f"Only {len(peer_metrics)} usable peer(s) were included; treat the median as "
            "a small-sample scenario."
        )

    complete_peer_set = (
        len(peer_metrics) >= 3
        and len(peer_metrics) == len(requested)
        and not peer_errors
        and subject_revenue is not None
        and subject_revenue > 0
        and subject_net_income is not None
        and subject_net_income > 0
        and len(earnings_multiples) == len(peer_metrics)
    )
    status: Literal["success", "partial"] = "success" if complete_peer_set else "partial"
    return ComparableValuation(
        status=status,
        requested_peer_tickers=requested,
        included_peer_tickers=[metric.ticker for metric in peer_metrics],
        peer_metrics=peer_metrics,
        median_price_to_sales=median_ps,
        median_price_to_earnings=median_pe,
        estimated_value_per_share_ps=estimated_ps,
        estimated_value_per_share_pe=estimated_pe,
        currency=company.currency,
        sources=_unique_sources(sources),
        summary=(
            f"Peer medians: P/S {median_ps:.2f}x"
            + (f", P/E {median_pe:.2f}x" if median_pe is not None else ", P/E unavailable")
            + ". Estimated per-share values use the subject company's latest annual revenue and "
            "positive net income when available."
        ),
        warnings=warnings,
    )


def _line_item(values: dict[str, float | None] | None, *labels: str) -> float | None:
    if not values:
        return None
    normalized = {_normalize(key): value for key, value in values.items()}
    for label in labels:
        value = normalized.get(_normalize(label))
        if value is not None and math.isfinite(value):
            return value
    return None


def _normalize(label: str) -> str:
    return "".join(character.lower() for character in label if character.isalnum())


def _unique_sources(sources: Sequence[DataSource]) -> list[DataSource]:
    unique: list[DataSource] = []
    seen: set[tuple[str, str | None]] = set()
    for source in sources:
        key = source.provider, source.url
        if key not in seen:
            seen.add(key)
            unique.append(source)
    return unique
