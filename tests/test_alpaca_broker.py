from __future__ import annotations

import httpx
import pytest

from src.execution.alpaca_broker import AlpacaBroker, OrderRequest


def test_dry_run_is_network_free() -> None:
    broker = AlpacaBroker("key", "secret")
    result = broker.submit(OrderRequest("AAPL", 2, "buy", "market"), dry_run=True)
    assert result["status"] == "dry_run"
    assert result["payload"]["client_order_id"]
    broker.close()


def test_limit_order_requires_price() -> None:
    broker = AlpacaBroker("key", "secret")
    with pytest.raises(ValueError, match="limit_price"):
        broker.submit(OrderRequest("AAPL", 2, "buy", "limit"), dry_run=True)
    broker.close()


def test_submit_posts_structured_order(monkeypatch: pytest.MonkeyPatch) -> None:
    broker = AlpacaBroker("key", "secret", base_url="https://example.test")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["json"] = request.read().decode()
        return httpx.Response(201, json={"id": "order-1", "status": "accepted"}, request=request)

    broker._client = httpx.Client(transport=httpx.MockTransport(handler), headers=broker._headers)
    result = broker.submit(OrderRequest("AAPL", 2, "buy", "market", client_order_id="research-1"), dry_run=False)
    assert result["id"] == "order-1"
    assert '"client_order_id":"research-1"' in str(seen["json"])
    broker.close()
