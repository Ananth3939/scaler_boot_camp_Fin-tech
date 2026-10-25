# Implementation decisions

## Local-first Python workflow

The research workflow runs in one process and returns typed, source-aware Pydantic results. The CLI, API, and Streamlit interface call the same workflow. Provider failures become warnings or partial results when useful output remains.

## Market data and news

The first adapter uses `yfinance` and Yahoo Finance. It sets bounded request timeouts, disables yfinance network retries, and keeps provider line-item labels. The provider does not guarantee consistent statement units, so DCF output is marked partial and warns users to verify units. News is limited to provider headlines and links; the sentiment result is a transparent keyword screen rather than article-level analysis.

Review Yahoo Finance terms and data limitations before redistributing this application or relying on its data.

## Model provider

The default provider is deterministic mock output so a local run needs no paid credentials. Amazon Bedrock is an optional adapter. It uses the AWS credential provider chain and configured model ID and region; model access and charges depend on the user's AWS account.

## API storage and exposure

The API binds to loopback by default and holds recent results in a bounded in-memory store. Restarting clears the store. Research routes support an optional bearer key and a bounded per-process rate limit; a non-loopback bind requires `API_KEY`. JSON request logs omit bodies, authorization headers, and query strings. Distributed rate limiting, durable storage, HTTPS termination, and production monitoring are not implemented, so the API is still intended for local use.

## MCP and A2A

MCP provides a read-only tool boundary for price, profile, statements, ratios, and news. Its local default transport is stdio.

A2A is deferred because the current specialist workflow has no separate service or cross-framework delegation requirement. Add an A2A service after a real deployment boundary exists, with authenticated tasks, bounded deadlines, and typed contracts.

## Valuation scope

The DCF uses available annual cash flow, cash, debt, and shares data; assumptions are explicit and the report includes growth/discount sensitivity. Comparable scenarios use user-selected peers, same-currency P/S and positive-earnings P/E medians, and subject-company revenue/earnings per share. The provider does not publish consistent statement-unit metadata; both valuation methods disclose that limitation and are illustrative scenarios, not fair-value estimates.

## Deployment and quality

The repository uses the MIT License. Docker and Compose are configured for a local API container, but the image has not been built in this environment because Docker is unavailable. CI runs deterministic pytest coverage, Ruff, and mypy. Request-level JSON logging is implemented; metrics, traces, distributed rate limits, authenticated deployment, and cloud infrastructure remain future work.
