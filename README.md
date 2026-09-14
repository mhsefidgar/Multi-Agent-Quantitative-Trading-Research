# Multi-Agent Quantitative Trading Research

A practical Python foundation for researching trading ideas, testing them, applying deterministic risk controls, and connecting approved orders to Alpaca.

The project is built to be **easy to run locally and straightforward to move toward cloud deployment**. It is not a live-trading system yet.

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

The important design rule is simple: **AI/research output cannot approve a trade.** The risk manager is deterministic and fail-closed.

### Included today

- LangGraph research workflow
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

Copy the example file:

```bash
cp .env.example .env
```

Then set the credentials you actually need.

For Alpaca paper trading:

```bash
ALPACA_API_KEY=your_paper_key
ALPACA_SECRET_KEY=your_paper_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

Do **not** commit `.env` or real API keys to Git. `.env.example` is intentionally safe to commit.

For local development, environment variables are enough. In AWS, use **AWS Secrets Manager** (or your organization's secret manager) and inject secrets into the container at runtime. Never put secrets directly in Terraform files, Dockerfiles, source code, or GitHub commits.

Other optional variables:

```bash
DATABASE_URL=postgresql://user:password@host:5432/dbname
WORKER_HEARTBEAT_SECONDS=30
LLM_API_KEY=your_provider_key
```

`LLM_API_KEY` is only relevant when an LLM provider adapter is enabled; the current deterministic workflow does not require one.

### 3. Run tests

```bash
ruff check .
mypy src
pytest -q
```

The broker tests do not need a real Alpaca account.

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

Create a paper-trading account with Alpaca and keep the credentials outside the repository.

```bash
export ALPACA_API_KEY="..."
export ALPACA_SECRET_KEY="..."
export ALPACA_BASE_URL="https://paper-api.alpaca.markets"
```

Keep `ALPACA_BASE_URL` pointed at the paper endpoint while developing.

The current broker adapter supports:

- market orders
- limit orders
- quantity/price validation
- `client_order_id`
- dry-run requests
- order lookup

A submitted order is not necessarily a filled order. Before live use, the system still needs durable order state, broker reconciliation, partial-fill handling, cancel/replace logic, restart recovery, and an operator kill switch.

## Run locally with Docker

Build the image:

```bash
docker build -t quant-engine:local .
```

Run it with your local environment file:

```bash
docker run --rm --env-file .env quant-engine:local
```

The image runs as a non-root user. The current `src.worker` is a safe long-running service shell that emits heartbeats and handles SIGTERM/SIGINT. It is **not yet a Kafka consumer**, so it should not be mistaken for a completed live trading worker.

## Run with PostgreSQL

The schema is in `src/storage/schema.sql` and includes research runs, factor observations, agent messages, orders, audit events and pgvector support.

```bash
psql "$DATABASE_URL" -f src/storage/schema.sql
```

For production, replace this one-shot schema setup with versioned migrations, automated backups, restore testing and a controlled migration process.

## Deploy to AWS

The repository includes a Terraform starting point for:

- ECS/Fargate
- ECR
- RDS PostgreSQL
- Amazon MSK/Kafka
- CloudWatch
- security groups
- IAM

The intended deployment is:

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

### Before deploying

Configure AWS credentials locally or, preferably for GitHub Actions, use OIDC rather than storing a long-lived AWS access key.

Validate Terraform first:

```bash
terraform -chdir=terraform init
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
terraform -chdir=terraform plan
```

Then deploy through your normal infrastructure process.

The existing GitHub Actions workflow is designed around an AWS OIDC role, an ECR image tagged with the Git commit SHA, and an ECS service update.

**Important:** the Terraform configuration is an infrastructure foundation, not a claim that the AWS environment is production-ready. IAM permissions, secret injection, RDS credentials, networking/egress, MSK connectivity, backups, alarms and recovery procedures still need environment-specific validation.

## Cloud deployment options

### AWS — recommended path in this repository

Use ECS/Fargate for the application, RDS for durable state, MSK for event delivery, Secrets Manager for credentials, ECR for images, and CloudWatch/OpenTelemetry for operations.

### Other platforms

The application is containerized, so the worker can also be adapted to another container platform such as Kubernetes, a managed container service, or a private VM environment. The same rules apply: secrets stay outside the image, state must be durable, and broker/execution state must survive restarts.

## Configuration model

Keep configuration separate from code:

| Variable | Purpose | Local | Cloud |
|---|---|---|---|
| `ALPACA_API_KEY` | Alpaca credential | `.env` | Secrets Manager |
| `ALPACA_SECRET_KEY` | Alpaca credential | `.env` | Secrets Manager |
| `ALPACA_BASE_URL` | Alpaca API endpoint | environment | task environment |
| `DATABASE_URL` | PostgreSQL connection | `.env` | secret/config injection |
| `LLM_API_KEY` | Optional LLM credential | `.env` | Secrets Manager |
| `WORKER_HEARTBEAT_SECONDS` | Worker setting | environment | task environment |

Do not use real credentials in examples, tests, Terraform variables committed to Git, or Docker image layers.

## Project structure

```text
src/
├── agents/
│   ├── graph.py
│   └── nodes.py
├── execution/
│   └── alpaca_broker.py
├── storage/
│   └── schema.sql
├── telemetry/
│   └── logging_tracing.py
└── worker.py

tests/
terraform/
.github/workflows/
Dockerfile
.env.example
architecture_schema.md
pyproject.toml
```

## Production status

This is a serious engineering foundation, but **it is not approved for live trading**.

The main remaining work is:

- durable market-data ingestion and Kafka consumers
- persistent execution/order state and idempotency
- broker reconciliation and restart recovery
- partial fills and cancel/replace state machines
- portfolio-level and liquidity risk controls
- stale-data and market-hours breakers
- kill switch and operational controls
- institutional-quality point-in-time backtesting
- walk-forward/out-of-sample validation and leakage controls
- real LLM provider integration if required
- production AWS IAM/secrets/network configuration
- security and dependency scanning
- deployment smoke tests and rollback
- alerts, SLOs and operational runbooks
- extended paper-trading validation before any live capital

The right progression is:

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