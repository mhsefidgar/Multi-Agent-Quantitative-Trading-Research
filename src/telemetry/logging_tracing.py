"""Structured logging, OpenTelemetry tracing, and Prometheus metrics."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from time import perf_counter
from typing import Any, Iterator

import structlog
from opentelemetry import trace
from opentelemetry.trace import Span
from prometheus_client import Counter, Histogram

agent_node_latency_seconds = Histogram("agent_node_latency_seconds", "Node latency", ["node_name"])
llm_token_usage_total = Counter("llm_token_usage_total", "LLM tokens consumed", ["model"])
backtest_sharpe_ratio_distribution = Histogram("backtest_sharpe_ratio_distribution", "Backtest Sharpe", buckets=(-2, -1, 0, .5, 1, 2, 3, 5, 10))
order_execution_slippage_bps = Histogram("order_execution_slippage_bps", "Execution slippage in bps")


def configure_logging() -> None:
    structlog.configure(processors=[structlog.contextvars.merge_contextvars, structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()], wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))


@contextmanager
def node_span(node_name: str, state: dict[str, Any]) -> Iterator[Span]:
    tracer = trace.get_tracer("quant-engine")
    started = perf_counter()
    with tracer.start_as_current_span(node_name) as span:
        trace_id = format(span.get_span_context().trace_id, "032x")
        structlog.contextvars.bind_contextvars(trace_id=trace_id, node_name=node_name, ticker=state.get("ticker"), severity="INFO")
        try:
            yield span
        finally:
            agent_node_latency_seconds.labels(node_name=node_name).observe(perf_counter() - started)
