"""Deterministic LangGraph orchestration for quantitative research."""
from __future__ import annotations

from typing import TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph

from .nodes import alpha_miner, backtester, bear_debate, bull_debate, execute_order, failure, risk_manager


class ResearchState(TypedDict, total=False):
    trace_id: str
    ticker: str
    bars: pd.DataFrame
    factor: pd.Series
    factor_name: str
    backtest: dict[str, float]
    bull: str
    bear: str
    risk: dict[str, object]
    order: dict[str, object]
    error: str
    dry_run: bool
    proposed_qty: float
    price: float
    portfolio_value: float


def route_after_risk(state: ResearchState) -> str:
    return "execution" if bool(state.get("risk", {}).get("approved")) else END


def build_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("alpha_miner", alpha_miner)
    graph.add_node("backtester", backtester)
    graph.add_node("bull_debate", bull_debate)
    graph.add_node("bear_debate", bear_debate)
    graph.add_node("risk_manager", risk_manager)
    graph.add_node("execution", execute_order)
    graph.add_node("failure", failure)

    graph.add_edge(START, "alpha_miner")
    graph.add_edge("alpha_miner", "backtester")
    graph.add_edge("backtester", "bull_debate")
    graph.add_edge("bull_debate", "bear_debate")
    graph.add_edge("bear_debate", "risk_manager")
    graph.add_conditional_edges("risk_manager", route_after_risk, {"execution": "execution", END: END})
    graph.add_edge("execution", END)
    graph.add_edge("failure", END)
    return graph.compile()


research_graph = build_graph()
