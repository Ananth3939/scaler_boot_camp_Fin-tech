from typing import Any

from finsight.models import ModelSummary


class MockLLMProvider:
    """Deterministic summary path that works without model credentials or network calls."""

    name = "mock"

    def summarize(self, context: dict[str, Any]) -> ModelSummary:
        ticker = str(context.get("ticker", "company"))
        price = context.get("stock_price")
        ratios = context.get("ratios")
        risks = context.get("risk_findings")
        valuation = context.get("valuation")

        sentences: list[str] = []
        if isinstance(price, dict):
            currency = price.get("currency") or "currency unavailable"
            sentences.append(
                f"{ticker}'s latest reported close is {currency} {float(price['close']):,.2f}."
            )
        else:
            sentences.append(f"A current price was unavailable for {ticker}.")

        if isinstance(ratios, dict) and ratios:
            ratio_text = ", ".join(
                f"{name.replace('_', ' ')} {float(value):.2f}" for name, value in ratios.items()
            )
            sentences.append(f"Available calculated ratios include {ratio_text}.")

        if isinstance(risks, list) and risks:
            sentences.append(
                "Risk checks reported: " + "; ".join(str(item) for item in risks) + "."
            )

        if isinstance(valuation, dict) and valuation.get("estimated_value_per_share") is not None:
            currency = valuation.get("currency") or "currency unavailable"
            sentences.append(
                "The illustrative DCF scenario is "
                f"{currency} {float(valuation['estimated_value_per_share']):,.2f} per share."
            )
        else:
            sentences.append("The DCF scenario was unavailable or not requested.")

        sentences.append("This is a deterministic mock summary, not investment advice.")
        return ModelSummary(
            provider=self.name,
            model_id="deterministic-mock",
            status="success",
            summary=" ".join(sentences),
            latency_ms=0,
            warnings=["LLM_PROVIDER=mock; no external language model was called."],
        )
