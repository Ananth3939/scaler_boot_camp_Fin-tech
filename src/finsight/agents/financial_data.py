from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import date
from typing import Literal

from finsight.models import FinancialStatements, RatioReport, RatioValue

_LINE_ITEM_ALIASES: dict[str, tuple[str, ...]] = {
    "revenue": ("Total Revenue", "Operating Revenue", "Revenue"),
    "gross_profit": ("Gross Profit",),
    "operating_income": ("Operating Income", "Operating Income or Loss"),
    "net_income": ("Net Income", "Net Income Common Stockholders"),
    "current_assets": ("Current Assets", "Total Current Assets"),
    "current_liabilities": ("Current Liabilities", "Total Current Liabilities"),
    "total_debt": ("Total Debt",),
    "equity": (
        "Stockholders Equity",
        "Total Stockholder Equity",
        "Total Equity Gross Minority Interest",
    ),
}


def compute_key_ratios(financial_data: FinancialStatements) -> RatioReport:
    """Calculate available ratios from the latest annual statement periods."""
    income = financial_data.income_statement[0] if financial_data.income_statement else None
    balance = financial_data.balance_sheet[0] if financial_data.balance_sheet else None
    values: dict[str, RatioValue] = {}
    warnings: list[str] = []

    _add_ratio(
        values,
        "gross_margin",
        "percent",
        "Gross Profit / Total Revenue × 100",
        _line_item(income.values if income else None, "gross_profit"),
        _line_item(income.values if income else None, "revenue"),
        income.period_end if income else None,
        multiplier=100,
    )
    _add_ratio(
        values,
        "operating_margin",
        "percent",
        "Operating Income / Total Revenue × 100",
        _line_item(income.values if income else None, "operating_income"),
        _line_item(income.values if income else None, "revenue"),
        income.period_end if income else None,
        multiplier=100,
    )
    _add_ratio(
        values,
        "net_profit_margin",
        "percent",
        "Net Income / Total Revenue × 100",
        _line_item(income.values if income else None, "net_income"),
        _line_item(income.values if income else None, "revenue"),
        income.period_end if income else None,
        multiplier=100,
    )
    _add_ratio(
        values,
        "current_ratio",
        "ratio",
        "Current Assets / Current Liabilities",
        _line_item(balance.values if balance else None, "current_assets"),
        _line_item(balance.values if balance else None, "current_liabilities"),
        balance.period_end if balance else None,
    )
    _add_ratio(
        values,
        "debt_to_equity",
        "ratio",
        "Total Debt / Stockholders' Equity",
        _line_item(balance.values if balance else None, "total_debt"),
        _line_item(balance.values if balance else None, "equity"),
        balance.period_end if balance else None,
    )

    required_ratios = {
        "gross_margin",
        "operating_margin",
        "net_profit_margin",
        "current_ratio",
        "debt_to_equity",
    }
    missing = sorted(required_ratios - set(values))
    if missing:
        warnings.append(
            "These ratios could not be calculated because required statement values were "
            "unavailable or had a zero denominator: " + ", ".join(missing)
        )
    warnings.extend(financial_data.warnings)
    return RatioReport(
        ticker=financial_data.ticker,
        values=values,
        source=financial_data.source,
        warnings=warnings,
    )


def _line_item(statement: Mapping[str, float | None] | None, logical_name: str) -> float | None:
    if statement is None:
        return None
    normalized = {_normalize_label(key): value for key, value in statement.items()}
    for alias in _LINE_ITEM_ALIASES[logical_name]:
        value = normalized.get(_normalize_label(alias))
        if value is not None and math.isfinite(value):
            return value
    return None


def _normalize_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]", "", label.lower())


def _add_ratio(
    results: dict[str, RatioValue],
    name: str,
    unit: Literal["percent", "ratio"],
    formula: str,
    numerator: float | None,
    denominator: float | None,
    period_end: date | None,
    multiplier: float = 1,
) -> None:
    if numerator is None or denominator is None or denominator == 0:
        return
    value = (numerator / denominator) * multiplier
    if not math.isfinite(value):
        return
    results[name] = RatioValue(
        value=value,
        unit=unit,
        formula=formula,
        period_end=period_end,
    )
