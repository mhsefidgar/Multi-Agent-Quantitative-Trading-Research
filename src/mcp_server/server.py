"""Model Context Protocol server for safe quantitative research operations."""
from __future__ import annotations

from typing import Any

import pandas as pd
from mcp.server.fastmcp import FastMCP

from src.agents.nodes import DEFAULT_LIMITS, RiskLimits, alpha_miner, backtester, risk_manager

mcp = FastMCP("quant-research")


def _bars(rows: list[dict[str, float]]) -> pd.DataFrame:
    if not rows:
        raise ValueError("bars must not be empty")
    return pd.DataFrame(rows)


@mcp.tool()
def generate_factor(bars: list[dict[str, float]]) -> dict[str, Any]:
    """Generate the deterministic momentum/volume research factor."""
    result = alpha_miner({"bars": _bars(bars)})
    factor = result["factor"]
    return {"factor_name": result["factor_name"], "factor": factor.tolist()}


@mcp.tool()
def run_backtest(
    bars: list[dict[str, float]],
    factor: list[float],
    spread_bps: float = 2.0,
    slippage_bps: float = 1.0,
    commission_bps: float = 0.5,
) -> dict[str, float]:
    """Run the deterministic cost-aware backtest."""
    frame = _bars(bars)
    if len(factor) != len(frame):
        raise ValueError("factor length must match bars length")
    result = backtester(
        {
            "bars": frame,
            "factor": pd.Series(factor, index=frame.index, dtype=float),
            "spread_bps": spread_bps,
            "slippage_bps": slippage_bps,
            "commission_bps": commission_bps,
        }
    )
    return result["backtest"]


@mcp.tool()
def evaluate_risk(
    ticker: str,
    proposed_qty: float,
    price: float,
    portfolio_value: float,
    estimated_var_fraction: float,
    backtest: dict[str, float],
    max_position_fraction: float = DEFAULT_LIMITS.max_position_fraction,
    max_var_fraction: float = DEFAULT_LIMITS.max_var_fraction,
    max_drawdown: float = DEFAULT_LIMITS.max_drawdown,
    min_sharpe: float = DEFAULT_LIMITS.min_sharpe,
    max_order_notional: float = DEFAULT_LIMITS.max_order_notional,
) -> dict[str, Any]:
    """Evaluate a proposed trade using the deterministic fail-closed policy."""
    limits = RiskLimits(
        max_position_fraction=max_position_fraction,
        max_var_fraction=max_var_fraction,
        max_drawdown=max_drawdown,
        min_sharpe=min_sharpe,
        max_order_notional=max_order_notional,
    )
    return risk_manager(
        {
            "ticker": ticker,
            "proposed_qty": proposed_qty,
            "price": price,
            "portfolio_value": portfolio_value,
            "estimated_var_fraction": estimated_var_fraction,
            "backtest": backtest,
        },
        limits=limits,
    )["risk"]


if __name__ == "__main__":
    mcp.run()
