# FinSight AI --- Multi-Agent Financial Research Platform

> An end-to-end learning project combining financial research agents,
> tool integration through MCP, agent-to-agent communication through
> A2A, and an optional Amazon Bedrock + Strands Agents deployment path.

**Status:** Runnable local CLI/API/UI, mock and Bedrock adapters, MCP, peer multiples, API controls, tests, Docker configuration, and CI quality gates. A2A and cloud deployment remain optional future work.\
**Primary language:** Python 3.11+\
**Local-first:** Yes\
**Cloud path:** AWS, Amazon Bedrock, and optionally Amazon Bedrock
AgentCore\
**Purpose:** Education and research only --- not investment, tax, or
legal advice.

------------------------------------------------------------------------

## 1. Project goal

Build a financial research application that accepts a company ticker
(for example, `AAPL`), collects market and company data, evaluates news
and sentiment, estimates valuation, assesses risk, and produces a
source-aware investment research brief.

The system uses specialist agents rather than one oversized prompt:

1.  **Financial Data Agent** --- statements, prices, and financial
    ratios.
2.  **News & Sentiment Agent** --- recent articles, source metadata, and
    sentiment.
3.  **Risk Agent** --- liquidity, leverage, volatility, and identified
    risk factors.
4.  **Valuation Agent** --- DCF assumptions and comparable-company
    multiples.
5.  **Report Writer Agent** --- combines the validated outputs into a
    final brief.
6.  **Orchestrator** --- validates inputs, manages dependencies,
    parallelizes independent work, handles failures, and assembles
    results.

The project should be built incrementally. Start with reliable Python
functions and typed results; add an LLM; then introduce MCP, A2A, a web
API, observability, and deployment.

## 2. Learning references

Use these two tutorials as the primary learning references:

-   [Finance Section 1 --- Finance AI
    agents](https://shrijankumar1-maker.github.io/finance-section-1/)
-   [How Agents Talk --- MCP and
    A2A](https://scaler-content.github.io/How-agents-talk/)

Additional implementation references:

-   [Strands Agents
    examples](https://d3ehv1nix5p99z.cloudfront.net/pr-cms-4813/examples/)
-   [Amazon Bedrock AgentCore
    documentation](https://docs.aws.amazon.com/bedrock-agentcore/)
-   [AWS sample: agent
    interoperability](https://github.com/aws-samples/sample-agent-interoperability)
-   [Google's MCP + A2A
    codelab](https://codelabs.developers.google.com/getting-started-mcp-a2a-adk?hl=en)

The reference tutorials are learning material; this repository is an
implementation plan inspired by their concepts, not a copy of their
source code.

## 3. Architecture

``` mermaid
flowchart TD
    U[User / CLI / Web UI] --> API[FastAPI application]
    API --> O[Research Orchestrator]
    O --> FD[Financial Data Agent]
    O --> NS[News and Sentiment Agent]
    O --> RK[Risk Agent]
    FD --> VAL[Valuation Agent]
    NS --> RW[Report Writer Agent]
    RK --> RW
    VAL --> RW
    RW --> OUT[Investment Research Brief]

    FD --> MCP[MCP Tool Server]
    NS --> MCP
    RK --> MCP
    MCP --> YF[yfinance / market-data adapter]
    MCP --> NEWS[News provider adapter]
    MCP --> CACHE[(TTL cache)]

    O -. optional remote delegation .-> A2A[A2A agent endpoints]
    A2A --> REMOTE[Remote specialist agents]

    API --> OBS[Logs, metrics, traces]
```

### Protocol boundaries

-   **MCP (Model Context Protocol):** agent-to-tool boundary. Use it to
    expose defined tools such as `get_stock_price`, `get_company_info`,
    `get_financial_statements`, and `search_news`.
-   **A2A (Agent2Agent):** agent-to-agent boundary. Use it when a
    specialist agent runs as a separate service and another agent needs
    to delegate a task to it.
-   **FastAPI:** application-facing HTTP API. It is not a replacement
    for MCP or A2A.
-   **Strands Agents + Amazon Bedrock (optional):** an AWS-oriented
    agent/model implementation path. Keep provider-specific code behind
    an adapter so the core application remains testable locally.

**Important:** Do not add network protocols just for the sake of it.
First implement the workflow in one process. Introduce MCP when tools
need a standard interface, and A2A when agents genuinely need
independent deployment or cross-framework communication.

## 4. Core workflow

1.  Validate ticker, date range, currency, and requested analysis.
2.  Fetch market/company data using a provider adapter.
3.  Run financial data, news, and risk analysis concurrently where
    independent.
4.  Pass required financial inputs to the valuation agent.
5.  Validate each agent's output against Pydantic schemas.
6.  Pass all findings and source references to the report writer.
7.  Return a structured JSON response and a readable Markdown report.
8.  Log duration, tool calls, cache hits, failures, and model usage
    without logging secrets.

If one agent fails, return a clearly marked partial result when safe. Do
not silently invent missing values. Distinguish unavailable data from
zero.

## 5. Suggested technology stack

  -----------------------------------------------------------------------
  Area                    Initial choice          Later extension
  ----------------------- ----------------------- -----------------------
  Language                Python 3.11+            Python 3.12+ after
                                                  dependency verification

  API                     FastAPI + Uvicorn       Authenticated API
                                                  gateway

  Schemas                 Pydantic                Versioned response
                                                  contracts

  Financial data          `yfinance` adapter      Licensed market-data
                                                  provider

  News                    Provider interface +    Search/news API with
                          mock data               source URLs

  Data analysis           pandas, NumPy           More robust financial
                                                  calculations

  LLM                     Provider adapter        Amazon Bedrock / Claude

  Agent framework         Plain Python first      Strands Agents SDK

  Tool protocol           Direct function calls   MCP server/client
                          first

  Agent protocol          In-process              A2A endpoints
                          orchestration first

  Cache                   In-memory TTL cache     Redis / managed cache

  UI                      CLI first               Streamlit or React

  Tests                   pytest                  Contract, integration,
                                                  and load tests

  Quality                 Ruff, mypy              CI quality gates

  Containers              Docker                  ECS/Fargate or
                                                  AgentCore where
                                                  appropriate

  Observability           Structured logs         OpenTelemetry, metrics,
                                                  traces
  -----------------------------------------------------------------------

Pin compatible package versions in the project lock file after verifying
the current installation instructions for each SDK.

## 6. Repository layout

Create this structure as the project grows:

``` text
finsight-ai/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── src/
│   └── finsight/
│       ├── __init__.py
│       ├── config.py
│       ├── api/
│       │   ├── main.py
│       │   └── routes.py
│       ├── schemas/
│       │   ├── requests.py
│       │   └── reports.py
│       ├── orchestration/
│       │   ├── workflow.py
│       │   └── tasks.py
│       ├── agents/
│       │   ├── financial_data.py
│       │   ├── news_sentiment.py
│       │   ├── risk.py
│       │   ├── valuation.py
│       │   └── report_writer.py
│       ├── tools/
│       │   ├── market_data.py
│       │   ├── news.py
│       │   └── cache.py
│       ├── protocols/
│       │   ├── mcp_server.py
│       │   └── a2a_service.py
│       ├── llm/
│       │   ├── base.py
│       │   ├── mock.py
│       │   └── bedrock.py
│       ├── services/
│       │   └── research.py
│       └── observability/
│           └── logging.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── contract/
├── data/
│   └── samples/
├── docs/
│   ├── architecture.md
│   ├── decisions.md
│   └── threat-model.md
└── scripts/
    ├── dev.sh
    └── smoke_test.sh
```

You do not need to create every module on day one. Add files when the
corresponding milestone is implemented.

## 7. Prerequisites

Install:

-   Git
-   Python 3.11 or newer
-   VS Code or another Python IDE
-   `curl` for API smoke tests
-   Docker, once containerization begins
-   AWS CLI only for the optional Bedrock path

Verify the local tools:

``` bash
git --version
python3 --version
python3 -m venv --help
```

On macOS with Homebrew, if Python is not installed:

``` bash
brew install python@3.12 git
```

Use a virtual environment; do not install project dependencies globally.

## 8. Local setup

``` bash
mkdir finsight-ai
cd finsight-ai
git init

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
```

For Windows PowerShell, activate with:

``` powershell
.\.venv\Scripts\Activate.ps1
```

Create `pyproject.toml` and add the selected dependencies. A starter
dependency set is:

``` text
fastapi
uvicorn[standard]
pydantic
pydantic-settings
yfinance
pandas
numpy
httpx
python-dotenv
pytest
pytest-asyncio
ruff
mypy
```

Install the dependencies after adding them to your project's dependency
configuration. Add the selected MCP, A2A, and Strands packages only when
reaching those milestones, using their current official installation
instructions.

## 9. Environment configuration

Create `.env.example`:

``` dotenv
APP_ENV=local
APP_NAME=FinSight AI
LOG_LEVEL=INFO

# Keep the default local implementation usable without a model API key.
LLM_PROVIDER=mock

# Optional AWS Bedrock configuration
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=
AWS_PROFILE=

# Optional cache and service settings
CACHE_TTL_SECONDS=300
REQUEST_TIMEOUT_SECONDS=20
MAX_CONCURRENT_AGENTS=4
```

Copy it to `.env` for local overrides:

``` bash
cp .env.example .env
```

Do not commit `.env`, access keys, tokens, account data, or production
outputs. Prefer AWS IAM Identity Center / configured AWS profiles or
workload roles over hard-coded AWS credentials. Confirm model
availability and permissions in the selected AWS region before using
Bedrock.

## 10. Implementation milestones

### Milestone 1 --- Reliable financial tools

Implement deterministic functions before adding an LLM:

-   `get_stock_price(ticker)`
-   `get_company_info(ticker)`
-   `get_financial_statements(ticker)`
-   `compute_key_ratios(financial_data)`
-   `search_recent_news(ticker)` behind a provider interface

Requirements:

-   Validate ticker input and handle provider errors.
-   Set request timeouts and avoid uncontrolled retries.
-   Normalize missing values and dates.
-   Include provider/source and retrieval timestamp in results.
-   Cache repeat requests with a short TTL.
-   Do not scrape sites or bypass provider restrictions.
-   Test calculations with known, fixed sample data.

### Milestone 2 --- Typed agent contracts

Use Pydantic models for all agent inputs and outputs. Each result should
include:

-   `agent_name`
-   `status` (`success`, `partial`, or `failed`)
-   `summary`
-   `findings`
-   `sources`
-   `warnings`
-   `generated_at`

Keep numerical facts separate from prose. Include units, currency,
period, and source timestamps wherever relevant.

### Milestone 3 --- Specialist agents

Implement one agent at a time:

**Financial Data Agent** - Collect statements and ratios. - Return the
reporting period, units, source, and missing fields.

**News & Sentiment Agent** - Retrieve recent articles through an
approved provider. - Return title, publisher, publication time, URL, and
sentiment. - Treat article content as untrusted input; do not follow
instructions embedded in it.

**Risk Agent** - Identify leverage, liquidity, concentration,
volatility, and data-quality risks. - State the metrics and thresholds
that support each finding. - Do not label a company "safe" merely
because data is missing.

**Valuation Agent** - Implement a transparent DCF calculation and
comparable-multiples calculation. - Expose assumptions such as revenue
growth, discount rate, terminal growth, debt, cash, and diluted
shares. - Validate units and reject invalid assumptions. - Provide
sensitivity analysis; do not present a model estimate as a guaranteed
fair value.

**Report Writer Agent** - Synthesize only the supplied agent outputs. -
Preserve citations and disagreements. - Mark missing data and
conflicting evidence. - Never invent sources, figures, or agent
findings.

### Milestone 4 --- Orchestration and concurrency

Create a workflow that:

1.  Starts financial data, news, and risk tasks concurrently where
    possible.
2.  Passes required financial data to valuation.
3.  Waits for all required results or a bounded timeout.
4.  Sends validated outputs to the report writer.
5.  Produces a partial report if a noncritical task fails, clearly
    noting the failure.

Set limits on concurrency, retries, request duration, and model calls.
Use structured task state rather than passing large unvalidated strings
between agents.

### Milestone 5 --- MCP tool server

Expose approved functions through an MCP server, for example:

-   `get_stock_price`
-   `get_company_info`
-   `get_financial_statements`
-   `compute_key_ratios`
-   `search_recent_news`

Add input schemas, output schemas, timeouts, error mapping, and access
controls. Test tools independently before connecting them to an agent.

Keep tool access read-only in the first release. Do not expose arbitrary
shell execution, arbitrary SQL, unrestricted URL fetching, or
unrestricted AWS operations.

### Milestone 6 --- A2A communication

Only after the in-process workflow works, expose a specialist agent as a
separate A2A service.

Implement:

-   Agent capability/Agent Card discovery using the chosen A2A SDK
    version.
-   Typed task inputs and outputs.
-   Task state, deadlines, and bounded retries.
-   Authentication and authorization for remote calls.
-   Correlation IDs for tracing a request across agents.
-   Contract tests between the caller and remote agent.

Start with one remote agent, such as News Agent or Valuation Agent. Keep
other agents local until remote communication provides a real benefit.

### Milestone 7 --- LLM integration

Create a model adapter so agents do not depend directly on one provider.

-   Start with a mock model for tests.
-   Add the selected provider's supported SDK.
-   For AWS, configure Amazon Bedrock, a permitted model ID, region, IAM
    permissions, and billing.
-   Request structured output where supported, then validate it with
    Pydantic.
-   Set token/output limits and timeouts.
-   Record model ID, latency, token usage where available, and errors.
-   Do not rely on an LLM to perform arithmetic that should be
    deterministic Python code.

If using Strands Agents, use the current official Strands documentation
and examples to connect the agent to Bedrock and MCP tools. Keep the
financial calculations in tested Python functions.

### Milestone 8 --- FastAPI service

Create endpoints such as:

``` text
GET  /health
POST /research
GET  /research/{request_id}
```

Example request:

``` json
{
  "ticker": "AAPL",
  "include_news": true,
  "include_valuation": true
}
```

The response should contain the report, structured agent results, source
links, timestamps, warnings, and a request ID. Validate request size and
input fields. Add authentication and rate limiting before exposing the
service outside localhost.

### Milestone 9 --- CLI or UI

Start with a CLI or API client. Then optionally add a Streamlit or React
interface that displays:

-   Company snapshot
-   Key ratios and financial periods
-   Recent news with source links
-   Risk findings
-   DCF assumptions and sensitivity analysis
-   Agent execution status
-   Final research brief and data-quality warnings

The UI should distinguish fetched facts, calculated metrics, and
LLM-generated commentary.

### Milestone 10 --- Tests and quality gates

Recommended tests:

-   Unit tests for ratio, DCF, and multiples calculations.
-   Schema tests for every agent result.
-   Mocked provider tests for missing data and timeouts.
-   Orchestration tests for concurrency and partial failures.
-   MCP tool contract tests.
-   A2A task and authentication tests.
-   API validation and error-response tests.
-   Regression fixtures for representative companies.
-   Prompt-injection tests using hostile article content.
-   Evaluation cases measuring factuality, citation coverage,
    completeness, latency, and cost.

Run:

``` bash
pytest -q
ruff check .
ruff format --check .
```

Configure the CI pipeline to run tests and static checks on every pull
request. Never use live market prices as exact unit-test expectations;
use deterministic fixtures.

### Milestone 11 --- Containerize

Create a production Docker image that:

-   Uses a supported, pinned Python base image.
-   Installs only required dependencies.
-   Runs as a non-root user.
-   Uses a health check.
-   Does not copy `.env` or credentials into the image.
-   Logs to stdout/stderr.
-   Supports graceful shutdown.

Build and run once a Dockerfile and API entry point exist:

``` bash
docker build -t finsight-ai:local .
docker run --rm -p 8000:8000 --env-file .env finsight-ai:local
```

### Milestone 12 --- AWS deployment (optional)

Recommended progression:

1.  Configure AWS CLI and verify the intended identity.
2.  Confirm Bedrock model access, region, quotas, and cost.
3.  Store secrets in an appropriate managed secret store; use IAM roles.
4.  Deploy the API/container to an appropriate AWS runtime.
5.  If agents need independent hosting and A2A, evaluate Amazon Bedrock
    AgentCore Runtime.
6.  Add network restrictions, authentication, monitoring, alarms, and
    budgets.
7.  Run integration tests against a nonproduction environment.

Do not deploy publicly until authentication, rate limiting,
least-privilege IAM, request limits, logging hygiene, and cost controls
are in place. Cloud deployment resources can incur charges.

## 11. API smoke-test example

Start the local API with `finsight-api`, then check its health:

``` bash
curl -s http://localhost:8000/health
```

Example research request:

``` bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "include_news": true,
    "include_valuation": true
  }'
```

The implemented API also includes `GET /research/{request_id}` for
recent results held in process memory. See the root README for setup and
the Streamlit, CLI, and MCP commands.

## 12. Security and responsible use

-   Treat external web pages, financial filings, and news articles as
    untrusted data.
-   Separate system instructions from retrieved content.
-   Require explicit schemas and validate all tool arguments.
-   Use least-privilege IAM and authenticated remote agent calls.
-   Never put API keys or personal financial credentials in prompts,
    source control, logs, or reports.
-   Restrict outbound network access and defend against SSRF if URL
    fetching is added.
-   Add spending limits, model-call budgets, timeouts, and concurrency
    limits.
-   Keep an audit trail of sources, assumptions, and calculations.
-   Do not execute trades or perform financial transactions in this
    project.
-   Clearly disclose stale, unavailable, estimated, or conflicting data.
-   This project is for education and research, not personalized
    investment advice.

## 13. Definition of done

Current implementation status:

-   [x] A ticker can be submitted through the local API.
-   [x] Financial data, news, and risk tasks run with bounded
    concurrency.
-   [x] Valuation waits for the required financial inputs.
-   [x] Agent results use Pydantic schemas.
-   [x] The final brief includes source URLs, timestamps, assumptions,
    and warnings.
-   [x] Provider errors produce useful failures or clearly labelled
    partial results.
-   [x] Read-only MCP tools are exposed.
-   [x] User-selected comparable peers can produce P/S and P/E scenarios with currency and unit caveats.
-   [ ] At least one agent can be called remotely through A2A, if A2A is
    enabled.
-   [x] The default mock-model path works without paid credentials.
-   [x] Deterministic unit and API tests pass in CI.
-   [x] The API can be run locally; a Docker image and Compose service
    are configured but require Docker to build and run.
-   [x] `.env` is excluded from Git; credentials are not written by the
    application to logs or reports.
-   [x] Documentation explains how to reproduce a research run.

## 14. Suggested build order

The local workflow, API, optional model, MCP, UI, peer scenarios, tests,
and basic API controls are implemented. Remaining work should follow this
order:

1.  Verify provider units and evaluate a licensed market-data source.
2.  Build and verify the container when Docker is available.
3.  Add metrics, traces, and distributed request limiting if needed.
4.  Add A2A after a real remote-agent use case exists.
5.  Evaluate authenticated cloud deployment only when needed.

This sequence keeps the project runnable throughout development and
makes debugging much easier.

## 15. Glossary

-   **Agent:** A model-driven component that uses instructions and tools
    to complete a bounded task.
-   **Tool:** A function or service an agent can invoke.
-   **MCP:** A standard interface for connecting applications/agents to
    tools and context.
-   **A2A:** A protocol for interoperable communication and task
    delegation between agents.
-   **Orchestrator:** The component responsible for task dependencies,
    execution, and result assembly.
-   **DCF:** Discounted cash flow valuation based on explicit
    assumptions about future cash flows and discounting.
-   **TTL cache:** A cache entry that expires after a configured
    time-to-live.
-   **Agent Card:** A machine-readable description of an A2A agent's
    identity and capabilities.

------------------------------------------------------------------------

## License

Choose a license before publishing or distributing the repository.
Review the terms of any data provider, model provider, and reference
repository used by your implementation.
