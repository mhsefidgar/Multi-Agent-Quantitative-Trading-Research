from __future__ import annotations

import numpy as np
import pandas as pd

from src.mcp_server.server import evaluate_risk, generate_factor, run_backtest


def _bars() -> list[dict[str, float]]:
    rng = np.random.default_rng(7)
    close = 100 * np.cumprod(1 + rng.normal(0.001, 0.005, 300))
    volume = rng.integers(1_000, 10_000, 300).astype(float)
    return pd.DataFrame({"close": close, "volume": volume}).to_dict("records")


def test_mcp_reuses_deterministic_factor_and_backtest() -> None:
    bars = _bars()
    factor = generate_factor(bars)
    assert factor["factor_name"] == "momentum_volume_z"
    metrics = run_backtest(bars, factor["factor"])
    assert set(metrics) >= {"sharpe", "sortino", "max_drawdown", "cost_bps"}


def test_mcp_risk_fails_closed_for_oversized_order() -> None:
    result = evaluate_risk(
        ticker="AAPL",
        proposed_qty=2_000,
        price=100.0,
        portfolio_value=100_000.0,
        estimated_var_fraction=0.01,
        backtest={"sharpe": 1.0, "max_drawdown": 0.05},
    )
    assert result["approved"] is False
    assert "position_limit" in result["reason"]
