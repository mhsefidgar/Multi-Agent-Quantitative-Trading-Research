# Multi-Agent Quantitative Trading Research

A practical Python foundation for researching trading ideas, testing them, applying deterministic risk controls, and connecting approved orders to Alpaca.

The project uses **LangGraph for internal workflow orchestration** and **Model Context Protocol (MCP) for the external tool boundary**. MCP is deliberately not placed in the latency-sensitive execution path.

## Architecture

```text
                    MCP clients / AI assistants
                              |
                    standard MCP tool boundary
                              |
                 +------------+-------------+
                 | quant-research MCP server |
                 +------------+-------------+
                              |
             +----------------+----------------+
             |                                 |
      deterministic research             deterministic risk
       factor / backtest                    evaluation
             |                                 |
             +----------------+----------------+
                              |
                         LangGraph
                              |
                     approved execution
                              |
                           Alpaca
```

The important safety rule remains: **AI/research output cannot approve a trade.** The risk manager is deterministic and fail-closed.

## MCP integration

The MCP server lives in `src/mcp_server/server.py` and exposes three narrowly scoped tools:

- `generate_factor` — deterministic momentum/volume factor generation
- `run_backtest` — deterministic cost-aware backtesting
- `evaluate_risk` — deterministic position, notional, VaR, drawdown and Sharpe checks

Execution is intentionally **not** exposed as an MCP tool. An MCP-connected model can request research and risk evaluation, but it cannot bypass the existing risk boundary or directly submit an order.

For local clients, the server uses MCP stdio transport:

```bash
pip install -e '.[dev]'
quant-mcp
```

The MCP dependency is pinned to the `1.x` compatibility range. MCP is an interoperability boundary, not the trading engine itself; the core Python functions remain directly callable for high-throughput research and execution workflows without serializing data through MCP.

## Performance and correctness decisions

- **No MCP calls inside the LangGraph hot path.** Existing deterministic functions remain local Python calls.
- **No DataFrame-as-MCP-resource conversion layer.** MCP receives explicit JSON-compatible rows and returns compact structured results.
- **No LLM authority over risk.** `evaluate_risk` calls the same fail-closed `risk_manager` used by the core graph.
- **No order-submission MCP tool.** Broker execution remains behind the deterministic approval boundary.
- **Reusable domain logic.** MCP adapters delegate to the existing factor, backtest and risk functions instead of duplicating trading logic.
- **Test coverage.** MCP calls are tested against the existing deterministic behavior and oversized-order rejection.

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

## Quick start

### 1. Install

Requirements: Python 3.11+, Git, and optionally Docker.

```bash
git clone https://github.com/mhsefidgar/Multi-Agent-Quantitative-Trading-Research.git
cd Multi-Agent-Quantitative-Trading-Research

python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1

pip install -e '.[dev]'
```

### 2. Run tests

```bash
ruff check .
mypy src
pytest -q
```

### 3. Run the MCP server

```bash
quant-mcp
```

Use an MCP-compatible client configured for a stdio server. The exposed tools are research/risk tools only; broker execution remains outside the MCP boundary.

## Production status

This is an engineering foundation, not an approved live-trading system. Before live capital, the project still needs durable market-data ingestion, persistent execution state, broker reconciliation, partial-fill handling, stale-data and market-hours breakers, a kill switch, stronger point-in-time backtesting, security scanning, deployment smoke tests, and extended paper-trading validation.

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
└── test_mcp_server.py
terraform/
.github/workflows/
Dockerfile
.env.example
architecture_schema.md
pyproject.toml
```
