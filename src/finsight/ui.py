from __future__ import annotations

from urllib.parse import urlsplit

import pandas as pd
import streamlit as st

from finsight.config import get_settings
from finsight.models import ResearchResponse
from finsight.orchestration.workflow import run_research

PEER_SHORTLIST = ["MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B"]


def main() -> None:
    st.set_page_config(
        page_title="FinSight | Company research",
        page_icon=":material/monitoring:",
        layout="wide",
    )
    _render_sidebar()
    _render_header()

    result = st.session_state.get("research_result")
    if isinstance(result, ResearchResponse):
        _render_result(result)
    else:
        _render_empty_state()


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## :material/monitoring: FinSight")
        st.caption("A focused workspace for company research")

        with st.form("research_request"):
            ticker_input = st.text_input(
                "Company ticker",
                value="AAPL",
                max_chars=15,
                help="Try AAPL, MSFT, NVDA, GOOGL, or AMZN.",
            )
            selected_peers = st.multiselect(
                "Compare with peers",
                options=PEER_SHORTLIST,
                default=["MSFT", "GOOGL", "AMZN"],
                help="Choose up to 10 peer tickers. You can add more below.",
            )
            custom_peers = st.text_input(
                "Other peers",
                placeholder="COST, WMT",
                help="Optional comma-separated tickers.",
            )
            include_news = st.toggle("Include recent headlines", value=True)
            include_valuation = st.toggle("Include DCF scenarios", value=True)
            submitted = st.form_submit_button(
                "Run research",
                type="primary",
                icon=":material/search:",
                width="stretch",
            )

        if submitted:
            ticker = ticker_input.strip().upper()
            peers = list(
                dict.fromkeys(
                    [
                        *selected_peers,
                        *(peer.strip().upper() for peer in custom_peers.split(",")),
                    ]
                )
            )
            peers = [peer for peer in peers if peer and peer != ticker]
            if not ticker:
                st.error("Enter a company ticker to start.")
            elif len(peers) > 10:
                st.error("Choose no more than 10 unique peer tickers.")
            else:
                try:
                    with st.spinner(f"Researching {ticker} and its peers…"):
                        st.session_state["research_result"] = run_research(
                            ticker,
                            get_settings(),
                            include_news=include_news,
                            include_valuation=include_valuation,
                            peer_tickers=peers,
                        )
                    st.toast(f"Research for {ticker} is ready", icon="✅")
                except ValueError as exc:
                    st.error(str(exc))

        st.caption("Data providers can return delayed or incomplete information.")


def _render_header() -> None:
    st.markdown(":green-badge[FINANCIAL RESEARCH WORKSPACE]")
    st.title("Company research, at a glance")
    st.caption(
        "Explore company fundamentals, risk signals, valuation scenarios, and recent headlines."
    )


def _render_empty_state() -> None:
    st.space("medium")
    with st.container(border=True):
        st.subheader("Start with a company ticker")
        st.write(
            "Use the research controls in the sidebar to build a sourced company brief. "
            "Add peer tickers to compare valuation multiples side by side."
        )
        first, second, third = st.columns(3)
        first.markdown("**:material/monitoring: Fundamentals**")
        first.caption("Price, market cap, and reported financial ratios")
        second.markdown("**:material/query_stats: Scenarios**")
        second.caption("Illustrative DCF sensitivity and peer multiples")
        third.markdown("**:material/newspaper: Headlines**")
        third.caption("Recent stories with source links and sentiment context")


def _render_result(result: ResearchResponse) -> None:
    company = result.company
    price = result.stock_price
    name = company.name if company and company.name else result.ticker

    with st.container(border=True):
        title_col, status_col = st.columns([4, 1], vertical_alignment="center")
        title_col.subheader(f"{name} ({result.ticker})")
        status_col.badge(
            result.status.title(),
            color={"success": "green", "partial": "orange", "failed": "red"}[result.status],
            icon=_status_icon(result.status),
        )
        st.caption(f"Generated {result.generated_at.astimezone().strftime('%Y-%m-%d %H:%M %Z')}")

    metric_columns = st.columns(4)
    metric_columns[0].metric(
        "Latest close",
        _money(price.close, price.currency) if price else "Unavailable",
        help=f"Market date: {price.as_of.isoformat()}" if price else None,
        border=True,
    )
    metric_columns[1].metric(
        "Market capitalization",
        _money(company.market_cap, company.currency) if company else "Unavailable",
        border=True,
    )
    metric_columns[2].metric(
        "Sector", company.sector if company and company.sector else "Unavailable", border=True
    )
    metric_columns[3].metric(
        "Industry", company.industry if company and company.industry else "Unavailable", border=True
    )

    if company and company.description:
        with st.expander("Company profile", icon=":material/info:"):
            st.write(company.description)

    overview_tab, valuation_tab, peers_tab, headlines_tab, report_tab = st.tabs(
        [
            ":material/space_dashboard: Overview",
            ":material/query_stats: Valuation",
            ":material/compare_arrows: Peers",
            ":material/newspaper: Headlines",
            ":material/description: Research brief",
        ]
    )
    with overview_tab:
        _render_overview(result)
    with valuation_tab:
        _render_valuation(result)
    with peers_tab:
        _render_comparables(result)
    with headlines_tab:
        _render_headlines(result)
    with report_tab:
        _render_report(result)

    st.caption(
        "For education and research only. Provider data may be delayed or incomplete. "
        "Valuation outputs are illustrative scenarios, not investment advice."
    )


def _render_overview(result: ResearchResponse) -> None:
    ratios_column, risk_column = st.columns([1.05, 1], gap="large")
    with ratios_column:
        st.subheader("Key ratios")
        if result.ratios and result.ratios.values:
            ratio_columns = st.columns(2)
            for index, (key, metric) in enumerate(result.ratios.values.items()):
                value = (
                    f"{metric.value:.2f}%" if metric.unit == "percent" else f"{metric.value:.2f}×"
                )
                ratio_columns[index % 2].metric(key.replace("_", " ").title(), value, border=True)
            for warning in result.ratios.warnings:
                st.caption(f"Data note · {warning}")
        else:
            st.info("No ratios were available from the returned financial statements.")

    with risk_column:
        st.subheader("Risk checks")
        if result.risk.findings:
            for finding in result.risk.findings:
                value = (
                    f"{finding.value:.1f}%"
                    if finding.unit == "percent"
                    else f"{finding.value:.2f} {finding.unit}"
                )
                color = {
                    "informational": "blue",
                    "moderate": "orange",
                    "high": "red",
                }[finding.severity]
                with st.container(border=True):
                    st.badge(finding.severity.title(), color=color)
                    st.markdown(f"**{finding.metric_name} · {value}**")
                    st.caption(f"{finding.explanation} Threshold: {finding.threshold}")
        else:
            st.info("No risk metrics were available for threshold checks.")
        for warning in result.risk.warnings:
            st.caption(f"Coverage note · {warning}")

    if result.warnings:
        with st.expander("Data quality notes", icon=":material/warning:"):
            for warning in result.warnings:
                st.warning(warning)


def _render_valuation(result: ResearchResponse) -> None:
    valuation = result.valuation
    st.subheader("Discounted cash flow scenario")
    if valuation.estimated_value_per_share is None:
        st.info(valuation.summary)
    else:
        estimate_col, status_col = st.columns([1, 2], vertical_alignment="center")
        estimate_col.metric(
            "Illustrative value per share",
            _money(valuation.estimated_value_per_share, valuation.currency),
            border=True,
        )
        status_col.write(valuation.summary)
        if valuation.assumptions:
            assumption_text = " · ".join(
                f"{label.replace('_', ' ').title()}: {value:.1%}"
                for label, value in valuation.assumptions.items()
                if "years" not in label
            )
            if assumption_text:
                st.caption(f"Model assumptions · {assumption_text}")

        if valuation.sensitivity:
            discount_rates = sorted({item.discount_rate for item in valuation.sensitivity})
            selected_discount = st.select_slider(
                "Adjust discount rate",
                options=discount_rates,
                value=discount_rates[len(discount_rates) // 2],
                format_func=lambda rate: f"{rate:.0%}",
                key=f"discount_rate_{result.request_id}",
            )
            scenarios = sorted(
                (item for item in valuation.sensitivity if item.discount_rate == selected_discount),
                key=lambda item: item.growth_rate,
            )
            chart_data = pd.DataFrame(
                {
                    "Growth rate": [f"{item.growth_rate:.0%}" for item in scenarios],
                    "Estimated value": [item.estimated_value_per_share for item in scenarios],
                }
            )
            st.line_chart(
                chart_data,
                x="Growth rate",
                y="Estimated value",
                y_label=f"Value per share ({valuation.currency or 'currency unavailable'})",
                alt="Illustrative DCF value per share across free cash flow growth assumptions",
            )
            st.dataframe(
                [
                    {
                        "Free cash flow growth": f"{item.growth_rate:.1%}",
                        "Discount rate": f"{item.discount_rate:.1%}",
                        "Estimate per share": _money(
                            item.estimated_value_per_share, valuation.currency
                        ),
                    }
                    for item in scenarios
                ],
                hide_index=True,
                width="stretch",
                alt="DCF sensitivity estimates for the selected discount rate",
            )
    for warning in valuation.warnings:
        st.caption(f"Valuation caveat · {warning}")


def _render_comparables(result: ResearchResponse) -> None:
    comparables = result.comparables
    st.subheader("Comparable-company analysis")
    st.caption(comparables.summary)
    if not comparables.peer_metrics:
        st.info("Choose peer tickers in the sidebar and run research to compare companies.")
        return

    metric_columns = st.columns(2)
    metric_columns[0].metric(
        "Median P/S", _multiple(comparables.median_price_to_sales), border=True
    )
    metric_columns[1].metric(
        "Median P/E", _multiple(comparables.median_price_to_earnings), border=True
    )
    scenario_columns = st.columns(2)
    if comparables.estimated_value_per_share_ps is not None:
        scenario_columns[0].metric(
            "P/S scenario per share",
            _money(comparables.estimated_value_per_share_ps, comparables.currency),
            border=True,
        )
    if comparables.estimated_value_per_share_pe is not None:
        scenario_columns[1].metric(
            "P/E scenario per share",
            _money(comparables.estimated_value_per_share_pe, comparables.currency),
            border=True,
        )

    available_multiples = {"Price to sales": "price_to_sales"}
    if any(peer.price_to_earnings is not None for peer in comparables.peer_metrics):
        available_multiples["Price to earnings"] = "price_to_earnings"
    selected_label = st.selectbox(
        "Compare peer multiples",
        options=list(available_multiples),
        key=f"peer_multiple_{result.request_id}",
    )
    selected_field = available_multiples[selected_label]
    peers = [
        (peer.ticker, getattr(peer, selected_field))
        for peer in comparables.peer_metrics
        if getattr(peer, selected_field) is not None
    ]
    chart_data = pd.DataFrame(
        {"Peer": [ticker for ticker, _ in peers], "Multiple": [value for _, value in peers]}
    )
    st.bar_chart(
        chart_data,
        x="Peer",
        y="Multiple",
        horizontal=True,
        x_label="Peer ticker",
        y_label=f"{selected_label} multiple (×)",
        alt=f"{selected_label} multiples across the selected peer companies",
    )
    st.dataframe(
        [
            {
                "Peer": peer.ticker,
                "Price to sales": f"{peer.price_to_sales:.2f}×",
                "Price to earnings": _multiple(peer.price_to_earnings),
                "Currency": peer.currency,
                "Statement period": peer.period_end.isoformat(),
            }
            for peer in comparables.peer_metrics
        ],
        hide_index=True,
        width="stretch",
        alt="Peer valuation multiples and statement periods",
    )
    for warning in comparables.warnings:
        st.caption(f"Comparable valuation caveat · {warning}")


def _render_headlines(result: ResearchResponse) -> None:
    sentiment = result.news_sentiment
    st.subheader("Recent headlines")
    st.caption(sentiment.summary)
    sentiment_columns = st.columns(3)
    sentiment_columns[0].metric("Positive", sentiment.positive_headlines, border=True)
    sentiment_columns[1].metric("Negative", sentiment.negative_headlines, border=True)
    sentiment_columns[2].metric("Neutral or mixed", sentiment.neutral_headlines, border=True)

    if result.news and result.news.articles:
        for article in result.news.articles:
            with st.expander(article.title, icon=":material/article:"):
                if _safe_https_url(article.url):
                    st.link_button("Open source article", article.url)
                st.caption(article.publisher or "Publisher unavailable")
                if article.published_at:
                    st.caption(f"Published {article.published_at:%Y-%m-%d %H:%M UTC}")
    else:
        st.info("No recent headlines were returned. Enable headlines in the sidebar and rerun.")

    if result.news:
        for warning in result.news.warnings:
            st.caption(f"News note · {warning}")
    for warning in sentiment.warnings:
        st.caption(f"Sentiment note · {warning}")


def _render_report(result: ResearchResponse) -> None:
    report_column, info_column = st.columns([1, 2], vertical_alignment="center")
    report_column.download_button(
        "Download research brief",
        data=result.markdown_report,
        file_name=f"{result.ticker.lower()}_research_brief.md",
        mime="text/markdown",
        icon=":material/download:",
        key=f"download_report_{result.request_id}",
    )
    info_column.caption(f"Request ID · `{result.request_id}`")

    with st.expander("Full research brief", expanded=True):
        st.markdown(result.markdown_report)
    with st.expander("Agent execution details"):
        for agent in result.agents:
            st.markdown(f"**{agent.agent_name} · {agent.status.title()}**")
            st.write(agent.summary)
            for finding in agent.findings:
                st.markdown(f"- {finding}")
            for warning in agent.warnings:
                st.caption(f"Note · {warning}")


def _status_icon(status: str) -> str:
    return {
        "success": ":material/check_circle:",
        "partial": ":material/warning:",
        "failed": ":material/error:",
    }[status]


def _money(value: float | None, currency: str | None) -> str:
    if value is None:
        return "Unavailable"
    return f"{currency or 'Currency unavailable'} {value:,.2f}"


def _multiple(value: float | None) -> str:
    return f"{value:.2f}×" if value is not None else "Unavailable"


def _safe_https_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


if __name__ == "__main__":
    main()
