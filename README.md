# Multi-Agent Quantitative Trading Research

A production-oriented foundation for building **auditable quantitative research and trading workflows** with LangGraph, Python, deterministic risk controls, Alpaca, PostgreSQL/pgvector, Kafka/MSK, and AWS.

> **Status: research / production-engineering foundation — not approved for live trading.**
>
> The repository deliberately separates research and agent reasoning from the rules that can authorize execution. The current code is useful for development, testing, paper trading, and architecture work, but several live-trading requirements still need to be implemented and validated.

## Why this project exists

Quantitative trading systems have two very different problems:

1. **Research:** generate signals, test ideas, compare assumptions, and explain why a strategy might work or fail.
2. **Execution:** protect the account, validate orders, survive failures, reconcile broker state, and leave an audit trail.

This project keeps those responsibilities separate. Agent/debate output is treated as research context. **It is never the authority that approves an order.** The risk manager is deterministic and fail-closed, and the execution node requires an explicit risk approval.

## What is included

### Research pipeline

- LangGraph orchestration
- Deterministic `momentum_volume_z` alpha baseline
- Backtest with one-period signal lag
- Spread, slippage, and commission assumptions
- Sharpe, Sortino, drawdown, alpha-decay, turnover/trade diagnostics
- Bull and bear research commentary nodes

### Risk and execution

- Position-size limit
- Maximum order notional
- Estimated VaR limit
- Drawdown breaker
- Minimum Sharpe requirement
- Input validation for quantities, prices, portfolio value, and ticker
- Deterministic risk decision hash
- Execution guard that blocks unapproved orders
- Typed Alpaca REST adapter
- Market and limit order payload validation
- Dry-run support
- `client_order_id` support
- Broker order lookup helper

### Engineering foundation

- Structured JSON logging with structlog
- Prometheus metrics
- OpenTelemetry spans
- PostgreSQL/pgvector schema
- HNSW vector index for factor observations
- Terraform baseline for ECS/Fargate, ECR, RDS PostgreSQL, MSK, IAM, security groups, and CloudWatch
- GitHub Actions quality/deployment workflow
- Non-root container image
- Long-running worker entry point with graceful SIGTERM/SIGINT handling
- Deterministic automated tests

## Architecture

```text
                         +------------------+
                         |   Market Data    |
                         +--------+---------+
                                  |
                                  v
                         +------------------+
                         |    Alpha Miner   |
                         +--------+---------+
                                  |
                                  v
                         +------------------+
                         |    Backtester    |
                         +--------+---------+
                                  |
                                  v
                         +------------------+
                         |   Bull / Bear    |
                         |    Research     |
                         +--------+---------+
                                  |
                                  v
                         +------------------+
                         | Rule-Based Risk  |
                         |  (fail closed)   |
                         +----+--------+----+
                              |        |
                           blocked   approved
                              |        |
                              v        v
                             END   +----------+
                                   | Execution|
                                   +----+-----+
                                        |
                                        v
                                   +---------+
                                   | Alpaca  |
                                   +---------+
```

Supporting infrastructure is designed around:

```text
GitHub Actions -> ECR -> ECS/Fargate
                         |
               +---------+---------+
               |                   |
             RDS                 MSK
          PostgreSQL            Kafka
               |
           pgvector
               |
        CloudWatch / OTEL
```

## Repository layout

```text
.
├── src/
│   ├── agents/
│   │   ├── graph.py                 # LangGraph topology and invocation
│   │   └── nodes.py                 # alpha, backtest, debate, risk, execution
│   ├── execution/
│   │   └── alpaca_broker.py         # typed Alpaca REST adapter
│   ├── storage/
│   │   └── schema.sql                # PostgreSQL + pgvector schema
│   ├── telemetry/
│   │   └── logging_tracing.py       # logging, metrics, tracing
│   └── worker.py                    # long-running container entry point
├── tests/
│   ├── test_alpaca_broker.py
│   ├── test_factor_baseline.py
│   ├── test_graph.py
│   └── test_risk_manager.py
├── terraform/
│   └── main.tf
├── .github/workflows/
│   └── deploy.yml
├── architecture_schema.md
├── Dockerfile
└── pyproject.toml
```

## Technology stack

| Area | Technology |
|---|---|
| Language | Python 3.11+ |
| Orchestration | LangGraph |
| Research | pandas, NumPy |
| Broker | Alpaca REST + httpx |
| Database | PostgreSQL 16 |
| Vector search | pgvector / HNSW |
| Messaging baseline | Amazon MSK / Kafka |
| Compute | AWS ECS Fargate |
| Registry | Amazon ECR |
| Secrets | AWS Secrets Manager |
| Logging | CloudWatch + structlog |
| Metrics | Prometheus client |
| Tracing | OpenTelemetry |
| Infrastructure | Terraform |
| CI/CD | GitHub Actions |

## Quick start

### Requirements

- Python 3.11+
- Git
- Optional: Docker
- Optional: Alpaca paper-trading account/credentials
- Optional for AWS: Terraform 1.6+, AWS account, VPC, private subnets, and deployment IAM/OIDC configuration

### Install locally

```bash
git clone https://github.com/mhsefidgar/Multi-Agent-Quantitative-Trading-Research.git
cd Multi-Agent-Quantitative-Trading-Research

python -m venv .venv
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -e '.[dev]'
```

### Run the checks

```bash
ruff check .
mypy src
pytest -q
```

The test suite does not require a live broker. Broker tests use an HTTP mock and verify request construction and validation locally.

## Run the research graph

The main application-level entry point is `run_research()` in `src/agents/graph.py`.

Example:

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

The graph runs in this order:

1. **Alpha Miner** — validates market data and calculates the baseline factor.
2. **Backtester** — evaluates the factor after transaction-cost assumptions.
3. **Bull Debate** — records the positive research case.
4. **Bear Debate** — records the failure case.
5. **Risk Manager** — evaluates deterministic policy checks.
6. **Execution** — runs only when risk explicitly approves.
7. **Failure** — converts unexpected graph failures into an explicit error state.

## Risk model

The default limits are intentionally simple and easy to inspect:

| Control | Default |
|---|---:|
| Maximum position | 10% of portfolio |
| Maximum estimated VaR | 2% |
| Maximum drawdown | 20% |
| Minimum Sharpe | 0.50 |
| Maximum order notional | $1,000,000 |

Approval requires every check to pass. For example, an order can be rejected because of position size even when the strategy has a good Sharpe ratio.

The risk manager also checks for malformed values such as NaN/infinite quantity, price, portfolio value, or VaR. A rejected decision includes the failed check names and a deterministic SHA-256 decision hash.

### Important safety boundary

The bull/bear agents cannot approve a trade. Their output is informational state. This is intentional: natural-language reasoning should not become an authorization channel for capital movement.

## Backtesting

The current backtester is a **baseline simulator**, not an institutional-grade research engine.

It currently includes:

- one-period lag to reduce direct look-ahead from the factor
- signal clipping to `[-1, 1]`
- spread cost
- slippage cost
- commission cost
- Sharpe ratio
- Sortino ratio
- maximum drawdown
- simple lag-1 alpha-decay diagnostic
- turnover-derived trade count
- total return

Example assumptions:

```python
{
    "spread_bps": 2.0,
    "slippage_bps": 1.0,
    "commission_bps": 0.5,
}
```

Before relying on results for capital allocation, add point-in-time data, corporate actions, survivorship-bias controls, market calendars, borrow/short constraints, realistic fill models, portfolio construction, liquidity limits, walk-forward validation, out-of-sample evaluation, leakage detection, and robustness tests.

## Alpaca paper trading

Set credentials in the environment rather than committing them to the repository:

```bash
export ALPACA_API_KEY="..."
export ALPACA_SECRET_KEY="..."
export ALPACA_BASE_URL="https://paper-api.alpaca.markets"
```

The broker adapter defaults to dry-run at the application call site. Keep paper trading enabled while validating the complete workflow.

Supported broker operations:

- market orders
- limit orders
- quantity and price validation
- generated or caller-supplied client order IDs
- dry-run requests
- order lookup

A successful order submission is **not** the same as a completed fill. A live system needs durable order state, reconciliation, partial-fill handling, cancel/replace logic, and restart recovery.

## Container / worker

The Docker image runs as a non-root user and starts `src.worker`.

Build and run locally:

```bash
docker build -t quant-engine:local .
docker run --rm quant-engine:local
```

The current worker is a safe long-running service shell: it emits heartbeats and handles termination signals. It does **not** claim to be a Kafka consumer yet. The durable event-processing implementation should be added before treating ECS as a live trading worker.

You can adjust the heartbeat interval with:

```bash
WORKER_HEARTBEAT_SECONDS=10
```

## PostgreSQL / pgvector

`src/storage/schema.sql` provides the persistence model for:

- `research_runs`
- `factor_observations`
- `agent_messages`
- `orders`
- `audit_events`

Factor observations include a 1536-dimensional vector column and an HNSW cosine index.

For a directly reachable database:

```bash
psql "$DATABASE_URL" -f src/storage/schema.sql
```

This SQL file is a schema baseline, not a complete migration system. Production should use a controlled migration tool, versioned migrations, migration history, backup/restore procedures, and tested rollback strategy.

## AWS / Terraform

The Terraform baseline covers:

- ECS cluster and Fargate service
- ECR repository with immutable tags and scan-on-push
- RDS PostgreSQL
- Amazon MSK
- CloudWatch log group
- security groups
- Secrets Manager placeholder
- IAM task role

The service is designed for private subnets without a public IP.

### Validate first

```bash
terraform -chdir=terraform init
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
```

Then plan with your environment-specific values:

```bash
terraform -chdir=terraform plan \
  -var='aws_region=us-east-1' \
  -var='vpc_id=vpc-xxxxxxxx' \
  -var='private_subnet_ids=["subnet-aaaa","subnet-bbbb"]' \
  -var='broker_secret_arn=arn:aws:secretsmanager:...'
```

Do not apply this baseline to a live trading environment until IAM, database credentials, secrets injection, network egress/VPC endpoints, MSK connectivity, ECS startup, backups, alarms, and operational recovery have been tested in a non-production environment.

## CI/CD

`.github/workflows/deploy.yml` currently covers:

### Validation

- Ruff
- mypy
- pytest
- factor baseline test

### Terraform

- formatting check
- initialization without a remote backend
- validation
- plan

### Container deployment

The deployment workflow uses GitHub OIDC to authenticate to AWS, builds an image, pushes a commit-SHA-tagged image to ECR, registers an ECS task definition, updates the service, and waits for ECS stability.

Typical configuration includes:

```text
AWS_REGION
VPC_ID
PRIVATE_SUBNET_IDS
BROKER_SECRET_ARN
ECR_REPOSITORY
ECS_CLUSTER
ECS_SERVICE
AWS_DEPLOY_ROLE_ARN
```

The exact values should be stored as GitHub environment/repository variables or secrets according to their sensitivity. AWS permissions should follow least privilege.

## Observability

The telemetry layer provides:

- JSON structured logs
- request/node trace context
- OpenTelemetry research and node spans
- node latency histogram
- LLM token usage counter
- backtest Sharpe histogram
- execution slippage histogram

The OpenTelemetry SDK/exporter dependencies are included, but an external OTLP exporter/provider still needs to be configured in the deployed runtime before traces are expected in a collector.

## Testing philosophy

The repository favors deterministic tests around the safety boundary.

Important cases include:

- malformed market data
- missing required columns
- oversized positions/orders
- excessive VaR
- excessive drawdown
- insufficient Sharpe
- NaN/infinite quantities
- execution without risk approval
- Alpaca dry-run behavior
- limit-order validation
- broker request construction
- deterministic factor/backtest behavior

The next testing layer for a production deployment should include integration tests against disposable infrastructure, Kafka failure tests, database recovery tests, broker reconciliation tests, network timeouts, duplicate delivery, container restarts, load tests, and controlled failure injection.

## Production readiness

This project is intentionally honest about what is and is not finished.

### Implemented

- [x] LangGraph orchestration
- [x] Deterministic alpha baseline
- [x] Cost-aware backtest baseline
- [x] Fail-closed deterministic risk manager
- [x] Execution authorization guard
- [x] Broker adapter and dry-run support
- [x] Client order ID support
- [x] Deterministic automated tests
- [x] PostgreSQL/pgvector schema
- [x] AWS infrastructure baseline
- [x] CI quality gates
- [x] Immutable container release tags
- [x] GitHub OIDC deployment pattern
- [x] Structured logging / metrics / tracing primitives
- [x] Long-running container entry point

### Still required before live trading

- [ ] Durable market-data ingestion with point-in-time semantics
- [ ] Real Kafka/MSK producer and consumer
- [ ] Durable research and execution persistence
- [ ] Versioned migration runner
- [ ] Durable idempotency across restarts
- [ ] Broker reconciliation and restart recovery
- [ ] Partial-fill and cancel/replace state machine
- [ ] Human/operator kill switch and trading halt path
- [ ] Portfolio-level exposure and concentration controls
- [ ] Liquidity and market-hours controls
- [ ] Stale-data and data-quality circuit breakers
- [ ] Realistic execution/fill simulation
- [ ] Walk-forward and out-of-sample validation
- [ ] Leakage, survivorship, and overfitting controls
- [ ] Real LLM provider integration if LLM reasoning is required
- [ ] Strict LLM output schemas, timeouts, budgets, and failure handling
- [ ] OTLP exporter/provider runtime configuration
- [ ] Production AWS IAM, RDS credential, backup, alarm, and network validation
- [ ] Security/dependency/container scanning
- [ ] GitHub Actions pinned to immutable SHAs
- [ ] Deployment smoke tests and automated rollback
- [ ] SLOs, alerts, runbooks, and incident procedures
- [ ] Paper-trading soak period and controlled production canary

## Recommended path from research to production

A practical rollout sequence is:

```text
1. Local deterministic tests
        |
2. Historical research + leakage checks
        |
3. Paper trading
        |
4. Durable persistence + broker reconciliation
        |
5. Event-driven AWS staging environment
        |
6. Failure injection / restart / duplicate-delivery tests
        |
7. Paper-trading soak test in staging
        |
8. Limited production canary
        |
9. Gradual capital and symbol expansion
```

Do not skip directly from a passing unit-test suite to live capital.

## Security notes

- Never commit Alpaca credentials or AWS credentials.
- Prefer AWS Secrets Manager for deployed secrets.
- Use short-lived GitHub OIDC credentials rather than long-lived cloud keys in CI.
- Keep the broker endpoint on the paper environment during development.
- Run the container as a non-root user.
- Apply least-privilege IAM.
- Keep trading and research permissions separated where possible.
- Treat logs and audit records as potentially sensitive operational data.
- Add dependency, image, IaC, and secret scanning before production deployment.

## Design documentation

See [`architecture_schema.md`](architecture_schema.md) for the workflow model, state contract, risk invariants, observability notes, and AWS architecture assumptions.

## Contributing

Keep changes small and reviewable. For changes affecting trading behavior or risk:

1. Add or update deterministic tests first.
2. Document the changed invariant or assumption.
3. Run `ruff`, `mypy`, and `pytest` locally.
4. Keep broker/API calls behind explicit adapters.
5. Never make natural-language agent output an authorization path.

## License

No license has been declared in the repository yet. Add an explicit open-source license before presenting the project as reusable open-source software.
