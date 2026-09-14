"""Long-running service entry point used by the container runtime.

The event-consumer integration is intentionally kept separate from the research
library. Until a durable queue consumer is configured, the worker stays alive
and emits periodic heartbeats instead of pretending that work was processed.
"""
from __future__ import annotations

import os
import signal
import time

from src.telemetry.logging_tracing import configure_logging
import structlog

_shutdown = False


def _request_shutdown(signum: int, _frame: object) -> None:
    global _shutdown
    _shutdown = True
    structlog.get_logger().info("worker_shutdown_requested", signal=signum)


def main() -> None:
    configure_logging()
    logger = structlog.get_logger().bind(service="quant-engine-worker")
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    interval = max(1.0, float(os.getenv("WORKER_HEARTBEAT_SECONDS", "30")))
    logger.info("worker_started", heartbeat_seconds=interval)

    while not _shutdown:
        logger.info("worker_heartbeat")
        time.sleep(interval)

    logger.info("worker_stopped")


if __name__ == "__main__":
    main()
