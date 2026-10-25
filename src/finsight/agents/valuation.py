from __future__ import annotations

import math
import re

from finsight.models import (
    CompanyProfile,
    FinancialStatements,
    ValuationResult,
    ValuationSensitivity,
)

DEFAULT_GROWTH_RATE = 0.05
DEFAULT_DISCOUNT_RATE = 0.10
DEFAULT_TERMINAL_GROWTH_RATE = 0.025
DEFAULT_PROJECTION_YEARS = 5


def calculate_dcf(
    statements: FinancialStatements | None,
    company: CompanyProfile | None,
    *,
    growth_rate: float = DEFAULT_GROWTH_RATE,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
    terminal_growth_rate: float = DEFAULT_TERMINAL_GROWTH_RATE,
    projection_years: int = DEFAULT_PROJECTION_YEARS,
) -> ValuationResult:
    assumptions = {
        "annual_free_cash_flow_growth": growth_rate,
        "discount_rate": discount_rate,
        "terminal_growth_rate": terminal_growth_rate,
        "projection_years": float(projection_years),
    }
    if not 0 <= growth_rate <= 0.5:
        raise ValueError("growth_rate must be between 0 and 0.5")
    if not 0 < terminal_growth_rate < discount_rate < 1:
        raise ValueError("require 0 < terminal_growth_rate < discount_rate < 1")
    if not 1 <= projection_years <= 10:
        raise ValueError("projection_years must be between 1 and 10")

    unavailable: list[str] = []
    if statements is None:
        unavailable.append("annual financial statements")
    if company is None or company.shares_outstanding is None:
        unavailable.append("shares outstanding")
    if company is None or company.currency is None:
        unavailable.append("company reporting currency")
    if unavailable:
        return _unavailable(assumptions, unavailable)

    assert statements is not None
    assert company is not None and company.currency is not None
    assert company.shares_outstanding is not None
    cashflow = statements.cash_flow[0] if statements and statements.cash_flow else None
    balance = statements.balance_sheet[0] if statements and statements.balance_sheet else None
    free_cash_flow = _line_item(cashflow.values if cashflow else None, "freecashflow")
    if free_cash_flow is None and cashflow is not None:
        operating_cash_flow = _line_item(cashflow.values, "operatingcashflow")
        capital_expenditure = _line_item(cashflow.values, "capitalexpenditure")
        if operating_cash_flow is not None and capital_expenditure is not None:
            # Yahoo generally represents capital expenditures as a negative cash-flow item.
            free_cash_flow = operating_cash_flow + capital_expenditure

    if free_cash_flow is None or free_cash_flow <= 0:
        unavailable.append("positive latest annual free cash flow")
    cash = _line_item(
        balance.values if balance else None,
        "cashandcashequivalentsandshortterminvestments",
        "cashandcashequivalents",
        "cashfinancial",
    )
    debt = _line_item(balance.values if balance else None, "totaldebt")
    if cash is None:
        unavailable.append("cash and short-term investments")
    if debt is None:
        unavailable.append("total debt")
    if unavailable:
        return _unavailable(assumptions, unavailable)

    assert free_cash_flow is not None
    assert cash is not None and debt is not None

    per_share = _dcf_per_share(
        free_cash_flow,
        cash,
        debt,
        company.shares_outstanding,
        growth_rate,
        discount_rate,
        terminal_growth_rate,
        projection_years,
    )
    if not math.isfinite(per_share):
        return _unavailable(assumptions, ["finite per-share output"])

    growth_step = min(0.02, growth_rate, 0.5 - growth_rate)
    discount_step = min(0.01, (discount_rate - terminal_growth_rate) / 2, (1 - discount_rate) / 2)
    growth_rates = sorted({growth_rate - growth_step, growth_rate, growth_rate + growth_step})
    discount_rates = sorted(
        {discount_rate - discount_step, discount_rate, discount_rate + discount_step}
    )
    sensitivity = [
        ValuationSensitivity(
            growth_rate=growth,
            discount_rate=discount,
            estimated_value_per_share=_dcf_per_share(
                free_cash_flow,
                cash,
                debt,
                company.shares_outstanding,
                growth,
                discount,
                terminal_growth_rate,
                projection_years,
            ),
        )
        for growth in growth_rates
        for discount in discount_rates
    ]

    return ValuationResult(
        status="partial",
        estimated_value_per_share=per_share,
        currency=company.currency,
        assumptions=assumptions,
        sensitivity=sensitivity,
        summary=(
            f"Illustrative DCF estimate: {company.currency} {per_share:,.2f} per share, "
            f"using latest reported free cash flow of {free_cash_flow:,.0f}."
        ),
        warnings=[
            "This is a scenario calculation, not a target price or investment recommendation.",
            "The growth, discount, and terminal growth rates are starter assumptions; change them "
            "for a company-specific analysis.",
            "Provider statement unit scaling is not explicitly guaranteed; verify the source "
            "period, currency, and units before relying on the per-share output.",
        ],
    )


def _dcf_per_share(
    free_cash_flow: float,
    cash: float,
    debt: float,
    shares_outstanding: float,
    growth_rate: float,
    discount_rate: float,
    terminal_growth_rate: float,
    projection_years: int,
) -> float:
    present_value = 0.0
    projected_fcf = free_cash_flow
    for year in range(1, projection_years + 1):
        projected_fcf *= 1 + growth_rate
        present_value += projected_fcf / ((1 + discount_rate) ** year)
    terminal_value = (
        projected_fcf * (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
    )
    present_value_terminal = terminal_value / ((1 + discount_rate) ** projection_years)
    enterprise_value = present_value + present_value_terminal
    equity_value = enterprise_value + cash - debt
    return equity_value / shares_outstanding


def _unavailable(assumptions: dict[str, float], inputs: list[str]) -> ValuationResult:
    return ValuationResult(
        status="unavailable",
        assumptions=assumptions,
        summary="DCF estimate unavailable because required data were missing.",
        warnings=["Missing valuation inputs: " + ", ".join(inputs) + "."],
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
    return re.sub(r"[^a-z0-9]", "", label.lower())
