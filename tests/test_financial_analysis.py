from __future__ import annotations

import pytest

from finsight.agents.comparables import calculate_comparable_valuation
from finsight.agents.financial_data import compute_key_ratios
from finsight.agents.valuation import calculate_dcf
from finsight.tools.market_data import normalize_ticker
from tests.factories import company, statements


def test_ratio_calculation_uses_statement_values() -> None:
    report = compute_key_ratios(statements("TEST"))

    assert report.values["gross_margin"].value == pytest.approx(40)
    assert report.values["operating_margin"].value == pytest.approx(20)
    assert report.values["net_profit_margin"].value == pytest.approx(10)
    assert report.values["current_ratio"].value == pytest.approx(2)
    assert report.values["debt_to_equity"].value == pytest.approx(0.2)


def test_ratio_calculation_leaves_zero_denominators_missing() -> None:
    financials = statements("TEST", revenue=0)
    report = compute_key_ratios(financials)

    assert "gross_margin" not in report.values
    assert any("zero denominator" in warning for warning in report.warnings)


def test_ticker_normalization_and_validation() -> None:
    assert normalize_ticker("  msft  ") == "MSFT"
    assert normalize_ticker("RELIANCE.NS") == "RELIANCE.NS"

    for value in ("", "TOO LONG TICKER", "AAPL/$"):
        with pytest.raises(ValueError):
            normalize_ticker(value)


def test_dcf_returns_base_case_and_sensitivity_grid() -> None:
    result = calculate_dcf(statements("TEST"), company("TEST"))

    assert result.status == "partial"
    assert result.estimated_value_per_share is not None
    assert len(result.sensitivity) == 9
    base = next(
        scenario
        for scenario in result.sensitivity
        if scenario.growth_rate == 0.05 and scenario.discount_rate == 0.10
    )
    assert base.estimated_value_per_share == pytest.approx(result.estimated_value_per_share)


def test_dcf_reports_missing_inputs_without_inventing_values() -> None:
    result = calculate_dcf(None, None)

    assert result.status == "unavailable"
    assert result.estimated_value_per_share is None
    assert result.sensitivity == []


def test_comparable_valuation_uses_peer_medians_and_subject_fundamentals() -> None:
    subject = company("SUBJ", market_cap=500, shares=10)
    subject_statements = statements("SUBJ", revenue=50, net_income=5)
    peers = [
        (company("PEER1", market_cap=120), statements("PEER1", revenue=60, net_income=6)),
        (company("PEER2", market_cap=200), statements("PEER2", revenue=100, net_income=10)),
    ]

    result = calculate_comparable_valuation(
        subject,
        subject_statements,
        peers,
        ["PEER1", "PEER2"],
    )

    assert result.status == "partial"
    assert result.median_price_to_sales == pytest.approx(2)
    assert result.median_price_to_earnings == pytest.approx(20)
    assert result.estimated_value_per_share_ps == pytest.approx(10)
    assert result.estimated_value_per_share_pe == pytest.approx(10)
    assert result.included_peer_tickers == ["PEER1", "PEER2"]


def test_comparable_valuation_excludes_currency_mismatches() -> None:
    result = calculate_comparable_valuation(
        company("SUBJ"),
        statements("SUBJ"),
        [(company("PEER", currency="EUR"), statements("PEER"))],
        ["PEER"],
    )

    assert result.status == "unavailable"
    assert result.peer_metrics == []
    assert any("does not match" in warning for warning in result.warnings)


def test_comparable_valuation_without_peers_is_not_requested() -> None:
    result = calculate_comparable_valuation(company("SUBJ"), statements("SUBJ"), [], [])

    assert result.status == "not_requested"
    assert result.peer_metrics == []
