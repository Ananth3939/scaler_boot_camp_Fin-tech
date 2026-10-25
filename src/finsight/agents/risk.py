from __future__ import annotations

import math
from statistics import stdev
from typing import Literal

from finsight.models import PriceHistory, RatioReport, RiskAssessment, RiskFinding


def assess_risk(
    ratios: RatioReport | None,
    price_history: PriceHistory | None = None,
) -> RiskAssessment:
    findings: list[RiskFinding] = []
    warnings = [
        "This first-pass assessment checks reported liquidity, leverage, and historical price "
        "volatility; concentration and qualitative risks are not assessed."
    ]

    if ratios is None:
        warnings.append(
            "Financial ratios were unavailable, so liquidity and leverage checks did not run."
        )
    else:
        current = ratios.values.get("current_ratio")
        if current is not None:
            severity: Literal["informational", "moderate", "high"] = (
                "high"
                if current.value < 1
                else "moderate"
                if current.value < 1.5
                else "informational"
            )
            findings.append(
                RiskFinding(
                    severity=severity,
                    metric_name="Current ratio",
                    value=current.value,
                    unit="ratio",
                    threshold=(
                        "Below 1.0 indicates current liabilities exceed current assets; "
                        "1.0–1.5 is a review range."
                    ),
                    explanation=(
                        f"Reported current ratio is {current.value:.2f}. "
                        + (
                            "It is below 1.0."
                            if current.value < 1
                            else "It is in the 1.0–1.5 review range."
                            if current.value < 1.5
                            else "It is above the 1.5 review threshold."
                        )
                    ),
                    period_end=current.period_end,
                )
            )

        leverage = ratios.values.get("debt_to_equity")
        if leverage is not None:
            severity = (
                "high"
                if leverage.value > 2
                else "moderate"
                if leverage.value > 1
                else "informational"
            )
            findings.append(
                RiskFinding(
                    severity=severity,
                    metric_name="Debt to equity",
                    value=leverage.value,
                    unit="ratio",
                    threshold="Above 1.0 is a review threshold; above 2.0 is a high leverage flag.",
                    explanation=(
                        f"Reported debt-to-equity ratio is {leverage.value:.2f}. "
                        + (
                            "It exceeds 2.0."
                            if leverage.value > 2
                            else "It is above 1.0."
                            if leverage.value > 1
                            else "It is at or below 1.0."
                        )
                    ),
                    period_end=leverage.period_end,
                )
            )
        if ratios.warnings:
            warnings.extend(ratios.warnings)

    volatility = _annualized_volatility(price_history)
    if volatility is not None and price_history is not None:
        ordered = sorted(price_history.points, key=lambda point: point.as_of)
        severity = "high" if volatility > 60 else "moderate" if volatility > 35 else "informational"
        findings.append(
            RiskFinding(
                severity=severity,
                metric_name="Annualized historical price volatility",
                value=volatility,
                unit="percent",
                threshold="Above 35% is a review threshold; above 60% is a high volatility flag.",
                explanation=(
                    f"Annualized standard deviation of adjusted daily returns is {volatility:.1f}% "
                    "over the available one-year window. This is historical variability, "
                    "not a forecast."
                ),
                period_start=ordered[0].as_of,
                period_end=ordered[-1].as_of,
            )
        )
    else:
        warnings.append(
            "Historical volatility could not be calculated from at least 21 daily closes."
        )

    if not findings:
        warnings.append(
            "No liquidity, leverage, or volatility metrics were available for threshold checks."
        )
    return RiskAssessment(
        status="partial",
        findings=findings,
        summary=(
            f"Completed {len(findings)} liquidity, leverage, and volatility threshold check(s)."
        ),
        warnings=warnings,
    )


def _annualized_volatility(price_history: PriceHistory | None) -> float | None:
    if price_history is None or len(price_history.points) < 21:
        return None
    ordered = sorted(price_history.points, key=lambda point: point.as_of)
    returns = [
        (current.close / previous.close) - 1
        for previous, current in zip(ordered, ordered[1:], strict=False)
        if previous.close > 0
    ]
    if len(returns) < 20:
        return None
    value = stdev(returns) * math.sqrt(252) * 100
    return value if math.isfinite(value) else None
