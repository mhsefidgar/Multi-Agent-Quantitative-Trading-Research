# Multi-Agent Quantitative Research & Trading Engine

## Topology

```text
Market Data -> Feature/Alpha Miner -> Candidate Factor
                                  |
                                  v
                         Backtest & Simulator
                                  |
                    +-------------+-------------+
                    |                           |
                 Bull Agent                  Bear Agent
                    |                           |
                    +-------------+-------------+
                                  |
                                  v
                         Rule-Based Risk Manager
                                  |
                       APPROVE / BLOCK / REDUCE
                                  |
                                  v
                         Execution Gateway
                                  |
                         Alpaca REST API
                                  |
                          Broker / Exchange

All components emit OpenTelemetry spans and Prometheus metrics.
A W3C trace_id is propagated through graph state, logs, HTTP headers,
and order metadata.
```

## State contract

`ResearchState` is the only object passed between graph nodes. It contains the ticker,
OHLCV data, candidate factor, backtest statistics, bull/bear opinions, risk decision,
execution payload, and immutable audit identifiers. Nodes return partial state updates;
no node mutates the shared state in place.

## Deterministic transitions

1. `alpha_miner` generates a bounded, vectorized factor from the supplied feature frame.
2. `backtester` runs the factor through the execution-aware simulator and computes Sharpe,
   Sortino, maximum drawdown, alpha decay, turnover, and trade count.
3. `bull_debate` and `bear_debate` independently score the same immutable research packet.
   Their outputs are advisory only.
4. `risk_manager` evaluates hard limits. It is pure Python, has no LLM dependency, and
   always runs after debate. A risk block cannot be overridden by an agent response.
5. `execution` is reachable only when `risk.approved == true`. It submits a typed order
   through the broker adapter; dry-run mode produces an auditable payload without sending it.
6. Any exception routes to `failure`, which records the error and prevents order submission.

```text
START -> ALPHA -> BACKTEST -> BULL -> BEAR -> RISK
                                                   |
                                  +----------------+----------------+
                                  |                                 |
                               BLOCK                            APPROVE
                                  |                                 |
                                END                              EXECUTE
                                                                    |
                                                                 END

Any node exception -> FAILURE -> END
```

## Risk invariants

The following rules are evaluated without an LLM and are fail-closed:

- maximum absolute position notional <= configured portfolio fraction;
- estimated one-day VaR <= configured portfolio fraction;
- projected drawdown must remain below the hard breaker;
- order quantity must be positive and finite;
- ticker must be allow-listed;
- strategy metrics must pass minimum Sharpe and maximum drawdown thresholds;
- broker must be reachable unless explicit dry-run mode is enabled.

The risk manager returns a rejection reason and a deterministic decision hash for auditability.

## Data and infrastructure

AWS ECS Fargate runs stateless API/worker services. Amazon RDS PostgreSQL stores research,
feature, and audit data with `pgvector` available for embeddings. Amazon MSK provides durable
market/order events. AWS Secrets Manager stores broker credentials. Terraform defines the
network, ECS, RDS, MSK, IAM, CloudWatch log group, and secrets resources.

## Observability

Every graph node creates a child span from the propagated trace context. LLM calls and vector
searches should use the same tracer. Logs are JSON and include `timestamp`, `trace_id`,
`node_name`, `ticker`, and `severity`. Prometheus metrics include node latency, LLM token use,
Sharpe observations, and execution slippage.

## Validation and release gates

- Unit tests verify risk invariants and graph transitions.
- Integration tests use mocked broker endpoints.
- Simulation tests include spread, configurable slippage, queue participation, and commission.
- Determinism tests submit adversarial LLM recommendations and assert the same risk result.
- CI runs Ruff, mypy, pytest, and the factor baseline gate before Terraform/deployment.
- Production deployment uses ECS rolling replacement and should be protected by GitHub environment
  approvals, least-privilege AWS OIDC, and a separate production account.
