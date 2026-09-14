"""Research, simulation, debate, and fail-closed risk nodes."""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.execution.alpaca_broker import AlpacaBroker, OrderRequest
from src.telemetry.logging_tracing import node_span


@dataclass(frozen=True)
class RiskLimits:
    max_position_fraction: float = 0.10
    max_var_fraction: float = 0.02
    max_drawdown: float = 0.20
    min_sharpe: float = 0.50
    max_order_notional: float = 1_000_000.0


DEFAULT_LIMITS = RiskLimits()


def alpha_miner(state: dict[str, Any]) -> dict[str, Any]:
    bars = state["bars"].copy()
    required = {"close", "volume"}
    if not required.issubset(bars.columns):
        raise ValueError(f"missing columns: {sorted(required - set(bars.columns))}")
    with node_span("alpha_miner", state):
        ret = bars["close"].pct_change()
        volume_z = (bars["volume"] - bars["volume"].rolling(20).mean()) / bars["volume"].rolling(20).std()
        factor = (ret.rolling(5).mean() * volume_z).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        return {"factor": factor, "factor_name": "momentum_volume_z"}


def backtester(state: dict[str, Any]) -> dict[str, Any]:
    with node_span("backtester", state):
        bars = state["bars"]
        signal = state["factor"].shift(1).clip(-1, 1)
        returns = bars["close"].pct_change().fillna(0.0)
        spread_bps = float(state.get("spread_bps", 2.0))
        slippage_bps = float(state.get("slippage_bps", 1.0))
        commission_bps = float(state.get("commission_bps", 0.5))
        turnover = signal.diff().abs().fillna(0.0)
        costs = turnover * (spread_bps + slippage_bps + commission_bps) / 10_000
        pnl = signal * returns - costs
        sharpe = float(np.sqrt(252) * pnl.mean() / pnl.std()) if pnl.std() > 0 else 0.0
        downside = pnl.where(pnl < 0, 0.0).std()
        sortino = float(np.sqrt(252) * pnl.mean() / downside) if downside > 0 else 0.0
        curve = (1 + pnl).cumprod()
        drawdown = curve / curve.cummax() - 1
        max_dd = float(abs(drawdown.min()))
        decay = float(abs(pnl.autocorr(lag=1))) if len(pnl) > 2 else 0.0
        return {"backtest": {"sharpe": sharpe, "sortino": sortino, "max_drawdown": max_dd, "alpha_decay": decay, "trades": float((turnover > 0).sum())}}


def bull_debate(state: dict[str, Any]) -> dict[str, str]:
    metrics = state["backtest"]
    return {"bull": f"Edge case: Sharpe={metrics['sharpe']:.3f}; seek persistence, liquidity and economic rationale."}


def bear_debate(state: dict[str, Any]) -> dict[str, str]:
    metrics = state["backtest"]
    return {"bear": f"Failure case: drawdown={metrics['max_drawdown']:.2%}; challenge costs, decay={metrics['alpha_decay']:.3f}, and regime dependence."}


def risk_manager(state: dict[str, Any], limits: RiskLimits = DEFAULT_LIMITS) -> dict[str, Any]:
    """Pure, fail-closed policy. No LLM output is consulted for approval."""
    with node_span("risk_manager", state):
        qty = float(state.get("proposed_qty", 0.0))
        price = float(state.get("price", 0.0))
        portfolio = float(state.get("portfolio_value", 0.0))
        bt = state.get("backtest", {})
        notional = abs(qty * price)
        checks = {
            "finite_positive_order": math.isfinite(qty) and qty > 0 and math.isfinite(price) and price > 0,
            "position_limit": portfolio > 0 and notional <= portfolio * limits.max_position_fraction,
            "order_notional_limit": notional <= limits.max_order_notional,
            "var_limit": float(state.get("estimated_var_fraction", 0.0)) <= limits.max_var_fraction,
            "drawdown_breaker": float(bt.get("max_drawdown", math.inf)) <= limits.max_drawdown,
            "minimum_sharpe": float(bt.get("sharpe", -math.inf)) >= limits.min_sharpe,
            "ticker_present": bool(state.get("ticker")),
        }
        approved = all(checks.values())
        reason = "approved" if approved else "; ".join(k for k, ok in checks.items() if not ok)
        decision_hash = hashlib.sha256(f"{state.get('ticker')}|{qty}|{price}|{checks}".encode()).hexdigest()
        return {"risk": {"approved": approved, "reason": reason, "checks": checks, "decision_hash": decision_hash}}


def execute_order(state: dict[str, Any]) -> dict[str, Any]:
    if not state.get("risk", {}).get("approved", False):
        raise PermissionError("execution reached without risk approval")
    broker = AlpacaBroker.from_environment()
    request = OrderRequest(symbol=state["ticker"], qty=state["proposed_qty"], side="buy", order_type="market", time_in_force="day")
    return {"order": broker.submit(request, dry_run=bool(state.get("dry_run", True)))}


def failure(state: dict[str, Any]) -> dict[str, Any]:
    return {"error": str(state.get("error", "unknown failure"))}
