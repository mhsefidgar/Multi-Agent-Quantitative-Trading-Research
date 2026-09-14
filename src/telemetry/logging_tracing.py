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
backtest_sharpe_ratio_distribution = Histogram(
    "backtest_sharpe_ratio_distribution", "Backtest Sharpe", buckets=(-2, -1, 0, 0.5, 1, 2, 3, 5, 10)
)
order_execution_slippage_bps = Histogram("order_execution_slippage_bps", "Execution slippage in bps")


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


def _bind_span_context(span: Span, node_name: str, state: dict[str, Any]) -> None:
    context = span.get_span_context()
    structlog.contextvars.bind_contextvars(
        trace_id=format(context.trace_id, "032x"),
        node_name=node_name,
        ticker=state.get("ticker"),
        severity="INFO",
    )


@contextmanager
def research_span(state: dict[str, Any]) -> Iterator[Span]:
    """Create the root span shared by every node in a research invocation."""
    tracer = trace.get_tracer("quant-engine")
    with tracer.start_as_current_span("research_graph") as span:
        _bind_span_context(span, "research_graph", state)
        yield span


@contextmanager
def node_span(node_name: str, state: dict[str, Any]) -> Iterator[Span]:
    tracer = trace.get_tracer("quant-engine")
    started = perf_counter()
    with tracer.start_as_current_span(node_name) as span:
        _bind_span_context(span, node_name, state)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            raise
        finally:
            agent_node_latency_seconds.labels(node_name=node_name).observe(perf_counter() - started)
