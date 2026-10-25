from __future__ import annotations

from urllib.parse import urlsplit

import streamlit as st

from finsight.config import get_settings
from finsight.models import ResearchResponse
from finsight.orchestration.workflow import run_research


def main() -> None:
    st.set_page_config(page_title="FinSight AI", page_icon="📈", layout="wide")
    st.title("FinSight AI")
    st.caption("Source-aware company research · Education and research only")

    with st.form("research_request"):
        ticker = st.text_input("Ticker", value="AAPL", max_chars=15).strip().upper()
        peer_text = st.text_input(
            "Peer tickers (optional, comma-separated)",
            placeholder="MSFT, GOOGL, AMZN",
        )
        left, right = st.columns(2)
        include_news = left.checkbox("Include recent news", value=True)
        include_valuation = right.checkbox("Include DCF scenario", value=True)
        submitted = st.form_submit_button("Run research", type="primary")

    if submitted:
        try:
            with st.spinner(f"Collecting available data for {ticker or 'ticker'}…"):
                st.session_state["research_result"] = run_research(
                    ticker,
                    get_settings(),
                    include_news=include_news,
                    include_valuation=include_valuation,
                    peer_tickers=[peer.strip() for peer in peer_text.split(",") if peer.strip()],
                )
        except ValueError as exc:
            st.error(str(exc))
            return

    result = st.session_state.get("research_result")
    if isinstance(result, ResearchResponse):
        _render_result(result)


def _render_result(result: ResearchResponse) -> None:
    st.divider()
    company = result.company
    price = result.stock_price
    name = company.name if company and company.name else result.ticker
    st.subheader(f"{name} ({result.ticker})")
    st.caption(
        f"Workflow status: **{result.status}** · Generated "
        f"{result.generated_at.astimezone().strftime('%Y-%m-%d %H:%M %Z')} · "
        f"Request ID: `{result.request_id}`"
    )

    columns = st.columns(4)
    columns[0].metric(
        "Latest close",
        _money(price.close, price.currency) if price else "Unavailable",
        help=f"Market date: {price.as_of.isoformat()}" if price else None,
    )
    columns[1].metric(
        "Market cap", _money(company.market_cap, company.currency) if company else "Unavailable"
    )
    columns[2].metric("Sector", company.sector if company and company.sector else "Unavailable")
    columns[3].metric(
        "Industry", company.industry if company and company.industry else "Unavailable"
    )

    if company and company.description:
        with st.expander("Company profile"):
            st.write(company.description)

    left, right = st.columns(2)
    with left:
        st.markdown("### Key ratios")
        if result.ratios and result.ratios.values:
            for key, metric in result.ratios.values.items():
                value = (
                    f"{metric.value:.2f}%" if metric.unit == "percent" else f"{metric.value:.2f}×"
                )
                st.metric(key.replace("_", " ").title(), value)
            for warning in result.ratios.warnings:
                st.caption(f"Data note: {warning}")
        else:
            st.info("No ratios were available from the returned financial statements.")

    with right:
        st.markdown("### Risk checks")
        if result.risk.findings:
            for finding in result.risk.findings:
                value = (
                    f"{finding.value:.1f}%"
                    if finding.unit == "percent"
                    else f"{finding.value:.2f} {finding.unit}"
                )
                st.write(f"**{finding.severity.title()} · {finding.metric_name}:** {value}")
                st.caption(f"{finding.explanation} Threshold: {finding.threshold}")
        else:
            st.info("No risk metrics were available for threshold checks.")
        for warning in result.risk.warnings:
            st.caption(f"Coverage note: {warning}")

    st.markdown("### Valuation scenario")
    valuation = result.valuation
    if valuation.estimated_value_per_share is not None:
        st.metric(
            "Illustrative DCF estimate per share",
            _money(valuation.estimated_value_per_share, valuation.currency),
        )
        st.caption(valuation.summary)
        if valuation.sensitivity:
            st.dataframe(
                [
                    {
                        "Free cash flow growth": f"{scenario.growth_rate:.1%}",
                        "Discount rate": f"{scenario.discount_rate:.1%}",
                        "Estimate per share": _money(
                            scenario.estimated_value_per_share, valuation.currency
                        ),
                    }
                    for scenario in valuation.sensitivity
                ],
                hide_index=True,
                use_container_width=True,
            )
    else:
        st.info(valuation.summary)
    for warning in valuation.warnings:
        st.caption(f"Valuation caveat: {warning}")

    st.markdown("### Comparable-company scenario")
    comparables = result.comparables
    st.caption(comparables.summary)
    if comparables.peer_metrics:
        comparison_values = []
        if comparables.estimated_value_per_share_ps is not None:
            comparison_values.append(
                (
                    "P/S scenario per share",
                    _money(comparables.estimated_value_per_share_ps, comparables.currency),
                )
            )
        if comparables.estimated_value_per_share_pe is not None:
            comparison_values.append(
                (
                    "P/E scenario per share",
                    _money(comparables.estimated_value_per_share_pe, comparables.currency),
                )
            )
        if comparison_values:
            metric_columns = st.columns(len(comparison_values))
            for column, (label, value) in zip(metric_columns, comparison_values, strict=True):
                column.metric(label, value)
        st.dataframe(
            [
                {
                    "Peer": metric.ticker,
                    "P/S multiple": f"{metric.price_to_sales:.2f}×",
                    "P/E multiple": (
                        f"{metric.price_to_earnings:.2f}×"
                        if metric.price_to_earnings is not None
                        else "Unavailable"
                    ),
                    "Currency": metric.currency,
                }
                for metric in comparables.peer_metrics
            ],
            hide_index=True,
            width="stretch",
            alt="Peer price-to-sales and price-to-earnings multiples",
        )
    for warning in comparables.warnings:
        st.caption(f"Comparable valuation caveat: {warning}")

    st.markdown("### Recent headlines")
    st.write(result.news_sentiment.summary)
    if result.news and result.news.articles:
        for article in result.news.articles:
            label = article.title[:180]
            if _safe_https_url(article.url):
                st.link_button(label, article.url)
            else:
                st.write(label)
            publisher = article.publisher or "Publisher unavailable"
            if article.published_at:
                publisher += f" · {article.published_at:%Y-%m-%d %H:%M UTC}"
            st.caption(publisher)
    else:
        st.info("No recent headlines were returned.")

    with st.expander("Agent execution details"):
        for agent in result.agents:
            st.markdown(f"**{agent.agent_name} · {agent.status}**")
            st.write(agent.summary)
            for finding_text in agent.findings:
                st.write(f"- {finding_text}")
            for warning in agent.warnings:
                st.caption(f"Note: {warning}")

    with st.expander("Full research brief"):
        st.markdown(result.markdown_report)

    if result.warnings:
        st.markdown("### Data quality and workflow warnings")
        for warning in result.warnings:
            st.warning(warning)

    st.caption(
        "Provider data may be delayed or incomplete. Calculations and DCF outputs are "
        "illustrative; "
        "this application does not provide investment advice."
    )


def _money(value: float | None, currency: str | None) -> str:
    if value is None:
        return "Unavailable"
    return f"{currency or 'Currency unavailable'} {value:,.2f}"


def _safe_https_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


if __name__ == "__main__":
    main()
