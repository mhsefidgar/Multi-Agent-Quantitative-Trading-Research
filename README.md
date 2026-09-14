# Multi-Agent Quantitative Trading Research

A practical Python foundation for **multi-agent quantitative trading research**, deterministic backtesting, risk evaluation, and controlled broker integration.

The project is designed as an engineering/research platform rather than a turnkey trading bot. It combines **LangGraph for internal workflow orchestration** with **Model Context Protocol (MCP) for the external research-tool boundary**. MCP is intentionally kept out of the latency-sensitive execution path.

> **Important:** This repository is **not approved for live trading**. The current implementation is suitable for local research, automated testing, paper-trading development, and infrastructure validation. Production deployment and live execution require additional controls described below.

## What this repository is about

The core idea is to separate **research intelligence** from **trade authorization**.

A research workflow can generate factors, run backtests, compare bull/bear interpretations, and propose an order. However, research or AI output is never allowed to approve a trade by itself. A deterministic risk layer evaluates the proposed action and fails closed when limits are not satisfied.

```text
Market data
    ↓
Alpha / factor research
    ↓
Cost-aware backtest
    ↓
Bull / bear research
    ↓
Deterministic risk checks
    ↓
Approval boundary
    ↓
Broker adapter
    ↓
Alpaca paper/live endpoint
```

The current implementation includes:

- LangGraph research workflow
- MCP research/risk tool boundary
- Deterministic momentum/volume alpha baseline
- Cost-aware backtesting
- Bull/bear research nodes
- Position, notional, VaR, drawdown and Sharpe checks
- Alpaca REST adapter with dry-run and paper-trading support
- PostgreSQL/pgvector schema
- Structured logs, Prometheus metrics and OpenTelemetry primitives
- Docker image and long-running worker entry point
- Terraform baseline for AWS ECS, ECR, RDS and MSK
- GitHub Actions validation for Python and Terraform

## Architecture

```text
MCP clients / AI assistants
          ↓
standard MCP tool boundary
          ↓
quant-research MCP server
      ↙             ↘
deterministic       deterministic
research            risk evaluation
      ↘             ↙
        LangGraph
            ↓
   deterministic approval
            ↓
          Alpaca
```

The key rule is:

**AI/research output cannot approve a trade. The risk manager is deterministic and fail-closed.**

## MCP integration

`src/mcp_server/server.py` exposes three narrowly scoped MCP tools:

- `generate_factor` — deterministic momentum/volume factor generation
- `run_backtest` — deterministic cost-aware backtesting
- `evaluate_risk` — deterministic position, notional, VaR, drawdown and Sharpe checks

Execution is intentionally **not** exposed as an MCP tool. MCP clients can request research and risk evaluation, but cannot bypass the existing risk boundary or directly submit an order.

Run the local MCP server over stdio:

```bash
pip install -e '.[dev]'
quant-mcp
```

The project uses the official Python MCP SDK in the `1.x` compatibility range. MCP is an interoperability boundary, not the trading engine: core functions remain directly callable for high-throughput workflows without MCP serialization/tool-call overhead.

### Performance and correctness decisions

- No MCP calls inside the LangGraph hot path; deterministic functions remain local Python calls.
- MCP adapters reuse existing factor, backtest and risk logic instead of duplicating trading rules.
- MCP inputs/outputs use explicit JSON-compatible structures rather than exposing internal pandas state.
- `evaluate_risk` invokes the same fail-closed `risk_manager` used by the core graph.
- No order-submission MCP tool is exposed.
- MCP integration tests cover deterministic research and oversized-order rejection.

## How professionals can use this repository

This repository is intended to be useful as a **research and engineering starting point** for quantitative developers, ML/AI engineers, trading-system engineers, researchers, and platform teams.

### Quant researchers

Use the repository to prototype and compare systematic ideas while keeping the research path reproducible:

1. Add or replace factor-generation logic.
2. Define explicit input data and assumptions.
3. Run cost-aware backtests rather than evaluating raw signals only.
4. Add statistical and economic diagnostics.
5. Compare research hypotheses through the existing workflow.
6. Preserve deterministic tests for every production-relevant research rule.

For serious research, professionals should add point-in-time datasets, corporate-action handling, realistic transaction costs, slippage/market-impact assumptions, walk-forward evaluation, out-of-sample testing, parameter-stability analysis, and controls against look-ahead or survivorship bias.

### Quant developers and trading engineers

Use the project as a foundation for separating:

- research and signal generation,
- deterministic risk decisions,
- order construction,
- broker connectivity,
- persistence and reconciliation,
- observability and operational controls.

The separation is intentional: changing an AI research component should not silently change the deterministic risk boundary or broker contract.

### AI/ML engineers

Use LangGraph and MCP where they add value without placing model calls in safety-critical execution paths. AI agents can help with research, hypothesis generation, summarization, scenario analysis, and tool selection, while deterministic code remains responsible for validation and authorization.

A professional deployment should treat model output as **untrusted input**. Validate schemas, constrain tool permissions, log model/tool decisions, and require deterministic checks before any external side effect.

### Platform / DevOps engineers

Use the Terraform and container configuration as an infrastructure starting point. The repository provides a baseline for AWS ECS/Fargate, ECR, RDS PostgreSQL, MSK/Kafka, CloudWatch, security groups, and IAM.

The infrastructure code is intentionally not presented as production-ready infrastructure. Teams should adapt it to their organization's network topology, IAM model, secrets management, observability standards, backup requirements, compliance controls, and disaster-recovery objectives.

### Teams evaluating the repository

A professional evaluation should distinguish three questions:

1. **Does the research logic work?** — covered by deterministic tests and backtests.
2. **Can the system fail safely?** — evaluate risk boundaries, invalid inputs, stale data, restart behavior, and broker failures.
3. **Can the system operate reliably?** — evaluate persistence, reconciliation, monitoring, alerting, deployment, rollback, and recovery procedures.

Passing unit tests alone is not evidence that a trading system is safe for production.

## Quick start

### 1. Install

Requirements: Python 3.11+, Git, and optionally Docker.

```bash
git clone https://github.com/mhsefidgar/Multi-Agent-Quantitative-Trading-Research.git
cd Multi-Agent-Quantitative-Trading-Research

python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

pip install -e '.[dev]'
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and set credentials as needed. For Alpaca paper trading:

```bash
ALPACA_API_KEY=your_paper_key
ALPACA_SECRET_KEY=your_paper_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

Do not commit `.env` or real API keys. In AWS, use Secrets Manager or your organization's secret manager and inject secrets at runtime.

Optional variables include `DATABASE_URL`, `WORKER_HEARTBEAT_SECONDS`, and `LLM_API_KEY`.

### 3. Run tests

```bash
ruff check .
mypy src
pytest -q
```

CI runs the same Ruff, mypy and pytest checks on pull requests, plus the factor baseline gate.

### 4. Run the MCP server

```bash
quant-mcp
```

Configure an MCP-compatible client for a stdio server. Research/risk tools only are exposed.

## Run the research workflow

The main entry point is `run_research()` in `src/agents/graph.py`.

```python
import numpy as np
import pandas as pd
from src.agents.graph import run_research

rng = np.random.default_rng(7)
close = 100 * np.cumprod(1 + rng.normal(0.001, 0.005, 300))
bars = pd.DataFrame({
    "close": close,
    "volume": rng.integers(1_000, 10_000, 300).astype(float),
})

result = run_research({
    "ticker": "AAPL",
    "bars": bars,
    "proposed_qty": 10,
    "price": float(close[-1]),
    "portfolio_value": 100_000,
    "dry_run": True,
})

print(result)
```

The graph validates market data, generates the factor, backtests it, creates research commentary, runs deterministic risk checks, and only then reaches execution.

## Alpaca keys and paper trading

Keep Alpaca credentials outside the repository and use the paper endpoint while developing:

```bash
export ALPACA_API_KEY="..."
export ALPACA_SECRET_KEY="..."
export ALPACA_BASE_URL="https://paper-api.alpaca.markets"
```

The broker adapter supports market/limit orders, validation, `client_order_id`, dry-run requests and order lookup. A submitted order is not necessarily a filled order; live use still requires durable order state, reconciliation, partial-fill handling, cancel/replace logic, restart recovery and an operator kill switch.

**Use paper trading before considering any production integration.** Never use production credentials simply to test the repository.

## Run locally with Docker

```bash
docker build -t quant-engine:local .
docker run --rm --env-file .env quant-engine:local
```

The image runs as a non-root user. `src.worker` is a safe long-running service shell with heartbeats and signal handling; it is not yet a Kafka consumer.

## Run with PostgreSQL

The schema is in `src/storage/schema.sql` and includes research runs, factor observations, agent messages, orders, audit events and pgvector support.

```bash
psql "$DATABASE_URL" -f src/storage/schema.sql
```

For production, replace this one-shot schema setup with versioned migrations, automated backups, restore testing and controlled migration processes.

## AWS infrastructure and deployment status

Terraform provides a starting point for ECS/Fargate, ECR, RDS PostgreSQL, Amazon MSK/Kafka, CloudWatch, security groups and IAM.

```text
GitHub Actions
      ↓
     ECR
      ↓
 ECS/Fargate
   ↙      ↘
 RDS      MSK
   ↘      ↙
 logs / metrics / traces
```

### Current status: deployment is intentionally disabled

GitHub Actions currently performs **validation only**. The Terraform job runs formatting, initialization without a backend, and validation. It does **not** provision AWS resources.

The repository contains a deployment job for future use, but that job is explicitly disabled until an AWS environment is deliberately provisioned and reviewed. This means the project does **not require AWS deployment credentials just to keep CI healthy today**.

When deployment is eventually enabled, configure and review at minimum:

- GitHub Actions OIDC with an AWS IAM role.
- A protected `production` GitHub Environment.
- `AWS_DEPLOY_ROLE_ARN` as an environment secret.
- `ECR_REPOSITORY`, `ECS_CLUSTER`, and `ECS_SERVICE` environment variables.
- Least-privilege IAM permissions for ECR and ECS, including any required `iam:PassRole` permissions.
- AWS networking, security groups, subnets, routing, encryption, logging, backups, and secrets management.
- Deployment smoke tests, health checks, rollback procedures, and operational alerts.

Prefer GitHub Actions OIDC over long-lived AWS access keys.

Validate Terraform locally before any future infrastructure change:

```bash
terraform -chdir=terraform init
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
terraform -chdir=terraform plan
```

The Terraform configuration is an infrastructure foundation, not a claim that the AWS environment is production-ready.

## Configuration model

| Variable | Purpose | Local | Cloud |
|---|---|---|---|
| `ALPACA_API_KEY` | Alpaca credential | `.env` | Secrets Manager |
| `ALPACA_SECRET_KEY` | Alpaca credential | `.env` | Secrets Manager |
| `ALPACA_BASE_URL` | Alpaca API endpoint | environment | task environment |
| `DATABASE_URL` | PostgreSQL connection | `.env` | secret/config injection |
| `LLM_API_KEY` | Optional LLM credential | `.env` | Secrets Manager |
| `WORKER_HEARTBEAT_SECONDS` | Worker setting | environment | task environment |

## Project structure

```text
src/
├── agents/
│   ├── graph.py
│   └── nodes.py
├── execution/
│   └── alpaca_broker.py
├── mcp_server/
│   ├── __init__.py
│   └── server.py
├── storage/
│   └── schema.sql
├── telemetry/
│   └── logging_tracing.py
└── worker.py

tests/
├── test_graph.py
├── test_mcp_server.py
└── test_alpaca_broker.py
terraform/
.github/workflows/
Dockerfile
.env.example
architecture_schema.md
pyproject.toml
```

## Production-readiness checklist

Before moving beyond research and controlled paper trading, a professional team should address at least:

### Research integrity

- Point-in-time market and fundamental data
- Corporate actions and symbol changes
- Look-ahead and survivorship-bias controls
- Walk-forward and out-of-sample validation
- Realistic commissions, spread, slippage, and market impact
- Parameter stability and sensitivity analysis
- Reproducible datasets and experiment metadata

### Trading and risk controls

- Persistent order and portfolio state
- Broker reconciliation and restart recovery
- Partial-fill and cancel/replace state machines
- Position, exposure, concentration, liquidity, and leverage limits
- Stale-data and market-hours breakers
- Maximum-loss and drawdown controls
- Operator kill switch
- Explicit handling of broker/API outages and rejected orders

### Production operations

- Versioned database migrations
- Durable market-data ingestion and Kafka consumers where required
- Secrets management and key rotation
- Least-privilege IAM
- Dependency and security scanning
- Structured audit trails
- Metrics, traces, logs, alerts, and SLOs
- Runbooks and incident-response procedures
- Deployment smoke tests and automated rollback
- Backup, restore, and disaster-recovery testing
- Controlled paper-trading soak tests before live exposure

## Intended progression

The safest progression is deliberate and measurable:

```text
local research
   → reproducible backtests
   → paper trading
   → durable staging
   → failure/recovery testing
   → paper-trading soak
   → controlled canary
   → gradual scale
```

Each stage should have explicit entry and exit criteria. Do not treat a successful backtest or green CI run as authorization for live trading.

## Design notes

See `architecture_schema.md` for the intended system architecture, state model and risk boundary.

## License

No license has been declared yet. Add a `LICENSE` file before distributing or accepting external contributions.
