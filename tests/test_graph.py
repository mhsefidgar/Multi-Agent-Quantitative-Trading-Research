from __future__ import annotations

import numpy as np
import pandas as pd

from src.agents.graph import run_research


def test_graph_fails_closed_on_invalid_market_data() -> None:
    state = {"ticker": "AAPL", "bars": pd.DataFrame({"close": [100.0], "bad_volume": [1.0]}), "dry_run": True}
    result = run_research(state)
    assert "error" in result
    assert "volume" in result["error"]


def test_graph_reaches_risk_and_blocks_oversized_order() -> None:
    rng = np.random.default_rng(7)
    close = 100 * np.cumprod(1 + rng.normal(0.001, 0.005, 300))
    bars = pd.DataFrame({"close": close, "volume": rng.integers(1000, 10000, 300).astype(float)})
    result = run_research(
        {
            "ticker": "AAPL",
            "bars": bars,
            "proposed_qty": 2000,
            "price": float(close[-1]),
            "portfolio_value": 100_000,
            "dry_run": True,
        }
    )
    assert result["risk"]["approved"] is False
    assert "position_limit" in result["risk"]["reason"]
    assert "order" not in result
