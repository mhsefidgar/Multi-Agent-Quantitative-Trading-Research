# Multi-Agent Quantitative Trading Research

Production-oriented reference architecture for a deterministic, auditable quantitative research and trading workflow built around LangGraph, Python, PostgreSQL/pgvector, Kafka/MSK, AWS ECS/Fargate, and Alpaca.

> **Current status: research/production-engineering scaffold — not production-ready for live trading.**
>
> The repository now contains the core orchestration, deterministic risk controls, broker adapter, tests, observability primitives, database schema, Terraform baseline, and CI/CD workflow. Before enabling live trading, the remaining production gates listed in [Production Readiness](#production-readiness) must be completed and validated in a real AWS environment.

## What this project does

The engine models a research-to-execution pipeline:

```text
Market Data
    |
    v
Alpha Miner -----> Backtester -----> Bull Debate -----> Bear Debate
                                                           |
                                                           v
                                                   Rule-Based Risk
                                                    /          \
                                               blocked        approved
                                                  |              |
                                                 END          Execution
                                                                  |
                                                                  v
                                                               Alpaca
```

The important design rule is that **LLM/agent commentary cannot approve an order**. Risk approval is computed by deterministic policy checks over validated state and backtest metrics. An execution node also refuses to run without an explicit approved risk decision.

## Core principles

- **Fail closed:** invalid market data, invalid quantities/prices, or failed research steps must not silently produce an executable order.
- **Deterministic risk:** position, notional, VaR, drawdown, Sharpe, and input-validity checks are evaluated by ordinary Python logic.
- **Auditable decisions:** risk decisions receive a deterministic decision hash; the SQL schema provides tables for research runs, agent messages, orders, and audit events.
- **Separation of concerns:** research/debate output is separated from the policy that controls execution.
- **Paper trading by default:** the Alpaca adapter supports dry-run operation and defaults to the Alpaca paper endpoint when configured from the environment.
- **Idempotent order intent:** orders support a `client_order_id`, allowing an application-level reconciliation layer to prevent duplicate submissions.
- **Observable execution:** structured logging, Prometheus metrics, and OpenTelemetry spans are included as observability primitives.
- **Immutable releases:** the CI/CD workflow builds and pushes container images using the Git commit SHA as the release tag.

## Repository layout

```text
.
├── src/
│   ├── agents/
│   │   ├── graph.py                 # LangGraph topology and invocation wrapper
│   │   └── nodes.py                 # alpha, backtest, debate, risk, execution
│   ├── execution/
│   │   └── alpaca_broker.py         # typed Alpaca REST adapter
│   ├── telemetry/
│   │   └── logging_tracing.py       # structlog, Prometheus, OpenTelemetry
│   └── storage/
│       └── schema.sql                # PostgreSQL + pgvector schema
├── tests/
│   ├── test_alpaca_broker.py        # broker contract tests
│   ├── test_factor_baseline.py      # deterministic factor baseline
│   ├── test_graph.py                # graph fail-closed/risk routing tests
│   └── test_risk_manager.py         # deterministic risk tests
├── terraform/
│   └── main.tf                      # AWS baseline: ECS, ECR, RDS, MSK, IAM, SGs
├── .github/workflows/
│   └── deploy.yml                   # lint/type/test/Terraform/build/deploy pipeline
├── architecture_schema.md           # architecture and risk invariants
├── Dockerfile                        # non-root Python container
└── pyproject.toml                    # Python package and tooling configuration
```

## Technology stack

| Area | Technology |
|---|---|
| Language | Python 3.11+ |
| Agent orchestration | LangGraph |
| Research | NumPy, pandas |
| Broker API | Alpaca REST via httpx |
| Database | PostgreSQL 16 |
| Vector search | pgvector / HNSW |
| Event backbone | Amazon MSK / Kafka baseline |
| Compute | AWS ECS Fargate |
| Container registry | Amazon ECR |
| Secrets | AWS Secrets Manager |
| Logs | CloudWatch Logs |
| Metrics | Prometheus client |
| Tracing | OpenTelemetry |
| IaC | Terraform |
| CI/CD | GitHub Actions |

## Important production-readiness statement

This repository should **not** be connected to a live brokerage account solely because the infrastructure and risk code exist.

Several components are intentionally still scaffolding:

1. The bull/bear nodes are deterministic research commentary, not a production LLM provider integration.
2. The backtester is a compact baseline simulator, not a full point-in-time institutional backtesting engine.
3. The database schema exists, but there is no migration runner or application persistence layer yet.
4. MSK is provisioned as infrastructure, but a Kafka producer/consumer/event-processing service is not implemented.
5. The Docker image currently runs a readiness print and exits; it is not yet a long-running production worker/service.
6. Terraform needs final AWS-environment validation, including ECS execution-role permissions and database credential management, before apply.
7. Broker reconciliation, durable idempotency, kill-switch controls, partial-fill handling, and recovery workflows need to be implemented before live execution.
8. CI validates Terraform and plans infrastructure, but production deployment still depends on correctly configured AWS/GitHub environment variables and an existing deployment role.
9. OpenTelemetry dependencies are present, but an OTLP exporter/provider configuration has not yet been wired into the runtime.
10. GitHub Actions are not yet pinned to immutable action SHAs.

Treat the project as a **production engineering foundation**, not as a finished live-trading platform.

## Quick start

### 1. Requirements

- Python 3.11 or newer
- Git
- Optional: Docker
- Optional for AWS deployment: Terraform 1.6+, AWS credentials/OIDC, an existing VPC with private subnets, and appropriate AWS permissions
- Optional for broker execution: Alpaca paper-trading credentials

### 2. Clone and install

```bash
git clone https://github.com/mhsefidgar/Multi-Agent-Quantitative-Trading-Research.git
cd Multi-Agent-Quantitative-Trading-Research

python -m venv .venv
source .venv/bin/activate       # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e '.[dev]'
```

### 3. Run the quality gates

```bash
ruff check .
mypy src
pytest -q
pytest -q tests/test_factor_baseline.py
```

The tests are designed to verify deterministic research behavior, fail-closed risk behavior, graph routing, and broker request construction without requiring a live Alpaca connection.

## Running the research graph

The primary entry point is `run_research()` in `src/agents/graph.py`.

A minimal dry-run invocation looks conceptually like this:

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

The graph executes:

1. `alpha_miner` — validates `close`/`volume` and computes the deterministic `momentum_volume_z` factor.
2. `backtester` — evaluates the factor with configurable spread, slippage, and commission assumptions.
3. `bull_debate` — generates a research-oriented positive case.
4. `bear_debate` — generates a research-oriented failure case.
5. `risk_manager` — evaluates deterministic policy limits.
6. `execution` — is reachable only when risk approval is true.
7. `failure` — returns an explicit error state when graph execution fails.

## Risk controls

The default `RiskLimits` are:

| Control | Default |
|---|---:|
| Maximum position fraction | 10% of portfolio |
| Maximum VaR fraction | 2% |
| Maximum drawdown | 20% |
| Minimum Sharpe | 0.50 |
| Maximum order notional | $1,000,000 |

Risk approval requires all of the following:

- finite positive quantity and price
- non-zero portfolio value
- position notional within the portfolio limit
- order notional below the absolute notional cap
- estimated VaR within the configured limit
- backtest drawdown within the configured breaker
- backtest Sharpe above the minimum
- a non-empty ticker

If any check fails, execution is blocked. The reason contains the failed policy checks and the decision is hashed for auditability.

### Why the debates cannot approve a trade

The bull and bear outputs are informational state. The risk manager does not inspect either output when deciding approval. This prevents prompt/agent text from becoming an implicit authorization path.

## Backtesting baseline

The current simulator uses:

- one-period-lagged factor signals
- bounded signals in `[-1, 1]`
- spread cost
- slippage cost
- commission cost
- Sharpe ratio
- Sortino ratio
- maximum drawdown
- simple alpha-decay/autocorrelation diagnostic
- turnover-derived trade count

Example cost parameters are passed in state:

```python
{
    "spread_bps": 2.0,
    "slippage_bps": 1.0,
    "commission_bps": 0.5,
}
```

For institutional use, this layer should be extended with point-in-time data, corporate actions, survivorship controls, borrow constraints, market calendars, realistic execution/fill models, portfolio construction, exposure constraints, and statistical validation against leakage and overfitting.

## Alpaca execution

The broker adapter is intentionally small and typed. It supports:

- market and limit orders
- quantity validation
- limit-price validation
- dry-run mode
- caller-supplied or generated `client_order_id`
- order lookup for reconciliation

### Environment variables

```bash
export ALPACA_API_KEY="..."
export ALPACA_SECRET_KEY="..."
export ALPACA_BASE_URL="https://paper-api.alpaca.markets"
```

Keep credentials outside source control. Use AWS Secrets Manager in deployed environments.

### Dry-run first

The application-level default is dry-run. A production rollout should progress through:

```text
unit tests -> deterministic backtests -> paper trading -> reconciliation tests
-> failure-injection tests -> limited production canary -> controlled scale-up
```

Do not treat a successful HTTP order submission as proof that the order was fully executed. Production execution needs durable order state and reconciliation against the broker.

## PostgreSQL and pgvector

`src/storage/schema.sql` defines the persistence model:

- `research_runs` — lifecycle and risk decision metadata
- `factor_observations` — factor values and optional 1536-dimensional embeddings
- `agent_messages` — research/debate messages
- `orders` — order intent and fill state with unique client order IDs
- `audit_events` — append-oriented operational/audit records

The schema enables an HNSW cosine index over factor embeddings.

### Applying the schema

The SQL file is a migration input, not an automated migration system. In an AWS environment, apply it using a controlled migration runner with appropriate database credentials and change tracking.

Example for a directly reachable PostgreSQL instance:

```bash
psql "$DATABASE_URL" -f src/storage/schema.sql
```

For production, use a proper migration tool/process and test migrations against the exact PostgreSQL/pgvector versions deployed in AWS.

## AWS architecture

The Terraform baseline provisions or configures:

- CloudWatch log group
- Secrets Manager broker secret placeholder
- task/data security groups
- private RDS PostgreSQL
- Amazon MSK Kafka
- ECS cluster with Container Insights
- ECR repository with immutable tags and scan-on-push
- ECS task definition
- ECS Fargate service
- ECS IAM task role

The ECS service is configured for private subnets and no public IP.

### Prerequisites

Before applying Terraform, provide:

- AWS account
- VPC ID
- at least the required private subnet IDs
- an AWS region
- broker secret ARN strategy
- network egress/NAT or required VPC endpoints for private ECS tasks
- IAM permissions for Terraform

Example variables:

```bash
terraform -chdir=terraform init
terraform -chdir=terraform validate
terraform -chdir=terraform plan \
  -var='aws_region=us-east-1' \
  -var='vpc_id=vpc-xxxxxxxx' \
  -var='private_subnet_ids=["subnet-aaaa","subnet-bbbb"]' \
  -var='broker_secret_arn=arn:aws:secretsmanager:...'
```

**Do not run `terraform apply` against production until the production-readiness gaps are closed.** In particular, validate ECS execution-role permissions, RDS credential management, secrets injection, container startup behavior, network egress, and MSK client connectivity in a non-production environment first.

## CI/CD

`.github/workflows/deploy.yml` currently provides three stages:

### Validation

Runs on pull requests and pushes to `main`:

- Ruff
- mypy
- pytest
- factor baseline test

### Terraform validation/plan

Runs on `main` after validation:

- Terraform formatting check
- Terraform initialization without a backend
- Terraform validation
- Terraform plan using GitHub Actions variables

### Container deployment

Runs on `main` after Terraform validation:

1. Authenticate to AWS using GitHub OIDC.
2. Build the Docker image.
3. Push an immutable `${GITHUB_SHA}` image to ECR.
4. Register an ECS task definition using that image.
5. Update the ECS service.
6. Wait for the ECS service to become stable.

### Required GitHub configuration

The workflow expects environment/repository configuration for values such as:

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

The exact GitHub `vars.*` and `secrets.*` placement should be configured according to the repository's security model. The AWS deploy role should trust GitHub's OIDC provider and have only the permissions required for the release process.

## Observability

The telemetry module provides:

### Structured logs

`structlog` emits JSON logs and binds trace ID, node name, ticker, and severity context.

### Prometheus metrics

Current metrics include:

- `agent_node_latency_seconds`
- `llm_token_usage_total`
- `backtest_sharpe_ratio_distribution`
- `order_execution_slippage_bps`

### OpenTelemetry

Research and node spans are created under the `quant-engine` tracer namespace, with a root `research_graph` span around graph invocation.

The OTLP SDK/exporter packages are declared, but exporter/provider configuration still needs to be wired into the deployed runtime before traces are expected in an external collector.

## Production readiness

### Already implemented

- [x] LangGraph research topology
- [x] Deterministic factor baseline
- [x] Backtest cost assumptions
- [x] Deterministic fail-closed risk manager
- [x] Execution guard requiring risk approval
- [x] Broker request validation
- [x] Dry-run support
- [x] Client order ID support
- [x] Broker order lookup helper
- [x] Unit and integration-style deterministic tests
- [x] PostgreSQL/pgvector schema baseline
- [x] AWS ECS/ECR/RDS/MSK Terraform baseline
- [x] CI quality gates
- [x] Immutable container release tags
- [x] OIDC-based AWS deployment pattern
- [x] Structured logs and telemetry primitives

### Required before live trading

- [ ] Replace the exiting Docker command with a real long-running worker/service.
- [ ] Implement real market-data ingestion and point-in-time data handling.
- [ ] Implement a real event pipeline using MSK/Kafka or another durable queue.
- [ ] Add durable persistence for every research run and execution transition.
- [ ] Add a production migration runner and migration history.
- [ ] Implement broker reconciliation, partial-fill handling, cancel/replace handling, and restart recovery.
- [ ] Make idempotency durable across process/container restarts.
- [ ] Implement a human/operational kill switch and trading halt path.
- [ ] Add account-level exposure, sector, liquidity, concentration, and market-hours controls as required.
- [ ] Add stale-data detection and data-quality circuit breakers.
- [ ] Add portfolio-level risk rather than only single-order checks.
- [ ] Add realistic transaction-cost and execution simulation.
- [ ] Add walk-forward/out-of-sample validation and leakage detection.
- [ ] Integrate and constrain a real LLM provider if LLM reasoning is required.
- [ ] Wire OpenTelemetry to an authenticated collector/exporter.
- [ ] Fix and validate ECS execution-role and secret permissions.
- [ ] Configure RDS credentials using managed/rotated secrets rather than unmanaged Terraform values.
- [ ] Add deployment rollback and automated smoke tests.
- [ ] Pin GitHub Actions to immutable commit SHAs.
- [ ] Add dependency/security scanning and container vulnerability gates.
- [ ] Add load, chaos, restart, network-failure, broker-failure, and duplicate-order tests.
- [ ] Establish operational alerts, SLOs, on-call ownership, and incident procedures.
- [ ] Validate all controls in paper trading before any production capital is exposed.

## Failure and recovery model

The intended safety boundary is:

```text
bad input / failed research
          |
          v
       failure
          |
         END

valid research
     |
     v
 deterministic risk
   /          \
blocked      approved
  |              |
 END          execution
                 |
                 v
             broker state
                 |
          reconciliation
```

The current graph invocation wrapper catches unexpected graph exceptions and converts them into a failure state. A complete production implementation should additionally persist the failure, emit an alertable event, and make recovery/replay semantics explicit.

## Security model

Never commit:

- Alpaca API keys
- AWS access keys
- database passwords
- OIDC/private signing material
- production account identifiers that are not intended to be public

Recommended deployment controls:

- GitHub OIDC instead of long-lived AWS keys
- least-privilege IAM roles
- Secrets Manager for broker/database secrets
- private ECS/RDS/MSK networking
- encrypted storage and transport
- immutable container tags
- dependency and image scanning
- mandatory pull-request review for risk-policy changes
- separate paper and production AWS/broker environments
- explicit approval gates for live execution

## Testing strategy

### Unit tests

Focus on pure functions and policy invariants:

- risk checks
- invalid quantity/price handling
- factor calculations
- cost calculations
- decision hashing

### Integration tests

Use mocked HTTP transports for broker contracts. Do not require real credentials in CI.

### Backtest regression

`tests/test_factor_baseline.py` provides a deterministic synthetic baseline so changes to factor logic can be detected by CI.

### Production certification tests

Before live trading, add tests for:

- broker timeout
- broker 5xx
- duplicate submission
- process restart after submission
- partial fill
- stale market data
- database outage
- Kafka outage
- telemetry outage
- invalid model/LLM output
- kill switch activation
- risk-limit changes
- concurrent order attempts

## Development workflow

A recommended change workflow is:

```text
1. Create branch
2. Change one bounded subsystem
3. Add/update deterministic tests
4. Run ruff + mypy + pytest locally
5. Run Terraform fmt/validate for infrastructure changes
6. Open pull request
7. Review risk/security implications
8. Merge only after CI passes
9. Deploy to non-production
10. Run paper-trading/smoke tests
11. Promote using an explicit production approval process
```

Risk policy changes should receive additional review because a seemingly small threshold or state change can alter execution behavior.

## Architecture documentation

See [`architecture_schema.md`](architecture_schema.md) for the workflow topology, state model, risk invariants, and infrastructure/observability design notes.

## License

No license is currently declared in the repository. Add an explicit license before treating the project as a distributable open-source package.
