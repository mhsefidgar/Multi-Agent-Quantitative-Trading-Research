# Multi-Agent Quantitative Trading Research

A practical Python foundation for researching trading ideas, testing them, applying deterministic risk controls, and connecting approved orders to Alpaca.

The project uses **LangGraph for internal workflow orchestration** and **Model Context Protocol (MCP) for the external tool boundary**. MCP is deliberately not placed in the latency-sensitive execution path. It is not a live-trading system yet.

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

The key rule remains: **AI/research output cannot approve a trade.** The risk manager is deterministic and fail-closed.

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

## What it does

```text
Market data
    ↓
Alpha signal
    ↓
Backtest
    ↓
Bull / Bear research
    ↓
Deterministic risk checks
    ↓
Approved order
    ↓
Alpaca
```

Included today:

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
- GitHub Actions CI/CD foundation

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

## Deploy to AWS

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

Prefer GitHub Actions OIDC over long-lived AWS access keys. Validate Terraform before deployment:

```bash
terraform -chdir=terraform init
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
terraform -chdir=terraform plan
```

The Terraform configuration is an infrastructure foundation, not a claim that the AWS environment is production-ready. IAM, secrets, networking, MSK connectivity, backups, alarms and recovery procedures still require environment-specific validation.

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

## Production status

This is a serious engineering foundation, but **it is not approved for live trading**.

Remaining work includes durable market-data ingestion and Kafka consumers; persistent execution/order state and reconciliation; partial fills and cancel/replace state machines; portfolio/liquidity risk controls; stale-data and market-hours breakers; kill switch and operational controls; institutional-quality point-in-time and walk-forward backtesting; production AWS IAM/secrets/network configuration; security/dependency scanning; deployment smoke tests and rollback; alerts/SLOs/runbooks; and extended paper-trading validation.

The intended progression is:

```text
local research
   → paper trading
   → durable staging
   → failure/recovery testing
   → paper-trading soak
   → controlled canary
   → gradual scale
```

## Design notes

See `architecture_schema.md` for the intended system architecture, state model and risk boundary.

## License

No license has been declared yet. Add a `LICENSE` file before distributing or accepting external contributions.
