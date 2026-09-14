from __future__ import annotations

import numpy as np
import pandas as pd

from src.agents.nodes import alpha_miner, backtester


def test_factor_baseline_is_finite_and_backtest_is_stable() -> None:
    rng = np.random.default_rng(7)
    close = 100 * np.cumprod(1 + rng.normal(0.0002, 0.01, 500))
    bars = pd.DataFrame({"close": close, "volume": rng.integers(1000, 10000, 500).astype(float)})
    state = {"bars": bars, "ticker": "TEST"}
    state.update(alpha_miner(state))
    result = backtester(state)["backtest"]
    assert np.isfinite(state["factor"]).all()
    assert np.isfinite(result["sharpe"])
    assert result["trades"] >= 0
