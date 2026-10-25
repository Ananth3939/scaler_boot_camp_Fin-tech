# FinSight AI

FinSight AI is a local-first financial research app. It fetches market and company data, calculates transparent ratios and risk indicators, screens recent headlines, and produces illustrative DCF and optional peer-multiple scenarios with a cited Markdown brief.

The app is for education and research, not investment, tax, or legal advice. Data from Yahoo Finance may be delayed, incomplete, or subject to provider terms. DCF values are scenarios; verify statement units and assumptions before relying on them.

## Current scope

- Typed data and agent results, source metadata, retrieval timestamps, warnings, bounded concurrency, and partial-result handling.
- CLI, localhost FastAPI API, and a Streamlit browser UI.
- Optional user-selected peer valuation using same-currency P/S and positive-earnings P/E medians.
- Optional read-only MCP server, defaulting to stdio.
- Deterministic mock model by default; optional Amazon Bedrock summary adapter.
- Optional bearer-key API authentication, bounded per-process rate limiting, a non-loopback bind guard, and structured request logs.
- Docker image and Compose configuration for the API, deterministic tests, and Ruff/mypy/pytest CI checks.

A2A is deferred until a specialist needs separate deployment. The API result store and rate limiter are in-memory and single-process; public deployment still needs HTTPS termination, managed secrets, durable storage, and production monitoring.

## Setup

Use Python 3.11 or newer and [uv](https://docs.astral.sh/uv/). Install every local adapter and development tool from the lockfile:

```bash
uv sync --all-extras
cp -n .env.example .env  # optional local settings; leaves an existing .env untouched
```

Activate the environment with `source .venv/bin/activate`, or run commands through `uv run`.

## Run a research brief

```bash
uv run finsight research AAPL
uv run finsight research MSFT --json
uv run finsight research AAPL --peers MSFT GOOGL AMZN
```

Other CLI commands are `price`, `company`, `statements`, `ratios`, and `news`. For example:

```bash
uv run finsight ratios AAPL
```

## Browser UI

```bash
uv run streamlit run src/finsight/ui.py
```

The research workspace uses sidebar controls and tabs for the overview, price performance and annual financials, valuation, peers, headlines, and report. Review one-year daily prices, switch among 1M/3M/6M/1Y windows, inspect reported revenue, income, cash flow, and balance-sheet values, adjust DCF sensitivity, switch peer charts between P/S and P/E, and download the brief as Markdown. The theme follows Streamlit's light/dark appearance setting.

## HTTP API

```bash
uv run finsight-api
```

Open `http://127.0.0.1:8000/docs`. The API provides `GET /health`, `POST /research`, and `GET /research/{request_id}`. Research results are held in a bounded in-memory store and expire; restarting the process clears them. The research routes are rate-limited. Set `API_KEY` in `.env` to require a bearer key; any non-loopback bind is rejected unless a key is configured.

```bash
curl -X POST http://127.0.0.1:8000/research \
  -H 'Content-Type: application/json' \
  -d '{"ticker":"AAPL","include_news":true,"include_valuation":true,"peer_tickers":["MSFT","GOOGL","AMZN"]}'
```

If `API_KEY` is set, add `-H 'Authorization: Bearer <your-api-key>'` to the curl command, replacing the placeholder with the value from `.env`. API request logs are JSON and omit request bodies, authorization headers, and query strings. Responses include an `X-Request-ID` header. The in-memory limiter is intended for one local process, not as a distributed production control.

## MCP tools

```bash
uv run finsight-mcp
```

The stdio server exposes read-only tools for stock price, company info, annual statements, key ratios, and recent news. A local Streamable HTTP server can be started with:

```bash
uv run finsight-mcp --transport streamable-http --host 127.0.0.1 --port 8001
```

## Optional Bedrock summaries

The default `LLM_PROVIDER=mock` requires no model credentials. To use Bedrock, set `LLM_PROVIDER=bedrock`, configure `AWS_REGION` and `BEDROCK_MODEL_ID`, and use an AWS profile or workload identity with model access:

```dotenv
LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=your-enabled-model-id
AWS_PROFILE=your-profile  # optional
```

Bedrock inference can incur charges. Do not put AWS credentials in `.env`; use your AWS credential provider chain.

## Container

The container runs the API as a non-root user and Compose publishes it only on localhost. Compose requires a key because the server binds inside the container to `0.0.0.0`:

```bash
cp -n .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
# Put the generated value on the API_KEY line in .env.
docker compose up --build
```

Docker must be installed and running. No cloud resources are created by this command.

## Quality checks

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

CI runs the deterministic unit/API suite plus Ruff and mypy. Live provider behavior is still subject to data availability and terms.

## License

This repository uses the MIT License; see [LICENSE](LICENSE).

## Architecture notes

See [README_FinSight_AI.md](README_FinSight_AI.md) for the original project blueprint and [docs/decisions.md](docs/decisions.md) for implementation boundaries and deferred work.
