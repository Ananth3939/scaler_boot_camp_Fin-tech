# FinSight AI

FinSight AI is a local-first financial research app. It fetches market and company data, calculates transparent ratios and risk indicators, screens recent headlines, and produces an illustrative DCF scenario with sensitivity values and a cited Markdown brief.

The app is for education and research, not investment, tax, or legal advice. Data from Yahoo Finance may be delayed, incomplete, or subject to provider terms. DCF values are scenarios; verify statement units and assumptions before relying on them.

## Current scope

- Typed data and agent results, source metadata, retrieval timestamps, warnings, bounded concurrency, and partial-result handling.
- CLI, localhost FastAPI API, and a Streamlit browser UI.
- Optional read-only MCP server, defaulting to stdio.
- Deterministic mock model by default; optional Amazon Bedrock summary adapter.
- Docker image and Compose configuration for the API, plus Ruff and mypy CI checks.

A2A, comparable-company valuation, a production authentication layer, a test suite, and public cloud deployment are not implemented. A2A is deferred until a specialist needs separate deployment. Public deployment needs additional security and operational work.

## Setup

Use Python 3.11 or newer and [uv](https://docs.astral.sh/uv/). Install every local adapter and development tool from the lockfile:

```bash
uv sync --all-extras
cp .env.example .env  # optional local settings
```

Activate the environment with `source .venv/bin/activate`, or run commands through `uv run`.

## Run a research brief

```bash
uv run finsight research AAPL
uv run finsight research MSFT --json
```

Other CLI commands are `price`, `company`, `statements`, `ratios`, and `news`. For example:

```bash
uv run finsight ratios AAPL
```

## Browser UI

```bash
uv run streamlit run src/finsight/ui.py
```

Enter a ticker to see the company snapshot, ratios, risk checks, DCF sensitivity, recent headlines, agent status, warnings, and full research brief.

## HTTP API

```bash
uv run finsight-api
```

Open `http://127.0.0.1:8000/docs`. The API provides `GET /health`, `POST /research`, and `GET /research/{request_id}`. Research results are held in a bounded in-memory store and expire; restarting the process clears them.

```bash
curl -X POST http://127.0.0.1:8000/research \
  -H 'Content-Type: application/json' \
  -d '{"ticker":"AAPL","include_news":true,"include_valuation":true}'
```

The API binds to loopback by default. It does not include authentication or rate limiting; keep it local until those controls are added.

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

The container runs the API as a non-root user and Compose publishes it only on localhost:

```bash
docker compose up --build
```

Docker must be installed and running. No cloud resources are created by this command.

## Quality checks

```bash
uv run ruff check .
uv run ruff format --check src/finsight
uv run mypy
```

The repository currently has CI for Ruff and mypy. Numerical research should be reviewed with deterministic fixtures before this project is used beyond learning; no automated test suite has been added yet.

## Architecture notes

See [README_FinSight_AI.md](README_FinSight_AI.md) for the original project blueprint and [docs/decisions.md](docs/decisions.md) for implementation boundaries and deferred work.
