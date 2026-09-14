"""Typed Alpaca REST adapter with dry-run, idempotency, and reconciliation helpers."""
from __future__ import annotations

import os
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Literal

import httpx

Side = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    qty: float
    side: Side
    order_type: OrderType
    time_in_force: str = "day"
    limit_price: float | None = None
    client_order_id: str | None = None


class BrokerError(RuntimeError):
    pass


class AlpacaBroker:
    def __init__(self, api_key: str, secret_key: str, base_url: str = "https://paper-api.alpaca.markets", timeout: float = 5.0) -> None:
        if not api_key or not secret_key:
            raise ValueError("Alpaca credentials are required")
        self.base_url = base_url.rstrip("/")
        self._headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}
        self._client = httpx.Client(timeout=timeout, headers=self._headers)

    @classmethod
    def from_environment(cls) -> "AlpacaBroker":
        return cls(
            os.environ["ALPACA_API_KEY"],
            os.environ["ALPACA_SECRET_KEY"],
            os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
        )

    @staticmethod
    def _payload(request: OrderRequest) -> dict[str, Any]:
        if request.qty <= 0:
            raise ValueError("quantity must be positive")
        if request.order_type == "limit" and (request.limit_price is None or request.limit_price <= 0):
            raise ValueError("limit orders require a positive limit_price")
        payload = asdict(request)
        if payload["limit_price"] is None:
            payload.pop("limit_price")
        if payload["client_order_id"] is None:
            payload.pop("client_order_id")
        return payload

    def submit(self, request: OrderRequest, *, dry_run: bool = True) -> dict[str, Any]:
        payload = self._payload(request)
        if dry_run:
            return {"status": "dry_run", "payload": payload}
        try:
            response = self._client.post(
                f"{self.base_url}/v2/orders",
                json=payload,
                headers={"X-Client-Order-ID": request.client_order_id or str(uuid.uuid4())},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise BrokerError(f"Alpaca order submission failed: {exc}") from exc
        return response.json()

    def get_order(self, order_id: str) -> dict[str, Any]:
        if not order_id:
            raise ValueError("order_id is required")
        try:
            response = self._client.get(f"{self.base_url}/v2/orders/{order_id}")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise BrokerError(f"Alpaca order reconciliation failed: {exc}") from exc
        return response.json()

    def close(self) -> None:
        self._client.close()
