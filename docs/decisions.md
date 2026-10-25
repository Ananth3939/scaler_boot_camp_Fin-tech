# Implementation decisions

## Local-first Python workflow

The research workflow runs in one process and returns typed, source-aware Pydantic results. The CLI, API, and Streamlit interface call the same workflow. Provider failures become warnings or partial results when useful output remains.

## Market data and news

The first adapter uses `yfinance` and Yahoo Finance. It sets bounded request timeouts, disables yfinance network retries, and keeps provider line-item labels. The provider does not guarantee consistent statement units, so DCF output is marked partial and warns users to verify units. News is limited to provider headlines and links; the sentiment result is a transparent keyword screen rather than article-level analysis.

Review Yahoo Finance terms and data limitations before redistributing this application or relying on its data.

## Model provider

The default provider is deterministic mock output so a local run needs no paid credentials. Amazon Bedrock is an optional adapter. It uses the AWS credential provider chain and configured model ID and region; model access and charges depend on the user's AWS account.

## API storage and exposure

The API binds to loopback and holds recent results in a bounded in-memory store. Restarting clears the store. Authentication, rate limiting, durable storage, and production monitoring are not implemented, so the API is for local use only.

## MCP and A2A

MCP provides a read-only tool boundary for price, profile, statements, ratios, and news. Its local default transport is stdio.

A2A is deferred because the current specialist workflow has no separate service or cross-framework delegation requirement. Add an A2A service after a real deployment boundary exists, with authenticated tasks, bounded deadlines, and typed contracts.

## Valuation scope

The DCF uses available annual cash flow, cash, debt, and shares data; assumptions are explicit and the report includes growth/discount sensitivity. Comparable-company valuation is deferred until a defensible peer set and consistent market-data source are available. Provider unit ambiguity means the DCF is an illustrative scenario, not a reliable fair-value estimate.

## Deployment and quality

Docker and Compose are configured for a local API container. No public cloud resources are created. CI currently runs Ruff and mypy. A deterministic automated test suite, production observability, authenticated deployment, and cloud infrastructure remain future work.
