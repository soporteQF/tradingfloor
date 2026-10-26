"""Tradovate Live Adapter — stub para integración futura.

Requiere credenciales Tradovate (demo o live) en .env:
  TRADOVATE_DEMO_URL=https://demo.tradovateapi.com
  TRADOVATE_DEMO_TOKEN=...
  TRADOVATE_USERNAME=...
  TRADOVATE_PASSWORD=...

Endpoints clave:
- POST /auth/accessTokenRequest
- POST /order/placeOrder
- GET /order/getOrders
- GET /position/getPositions
- WS /marketData/subscribe (para marks en tiempo real)

NOTA: Implementación completa requiere cuenta Tradovate aprobada.
Este stub lanza NotImplementedError con mensajes claros.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from .base import (
    ExecutionAdapter, Order, Position, Fill,
    OrderSide, OrderType, OrderStatus
)

log = logging.getLogger(__name__)


class TradovateExecutionAdapter(ExecutionAdapter):
    """Adapter Tradovate REST + WebSocket. Stub — implementar cuando haya credenciales."""

    def __init__(self, demo: bool = True):
        self.demo = demo
        self._connected = False
        self._session_token: Optional[str] = None
        self._account_id: Optional[int] = None
        raise NotImplementedError(
            "Tradovate adapter requiere credenciales y implementación completa. "
            "Usa PaperExecutionAdapter para desarrollo. "
            "Ver: https://github.com/tradovate/api-docs"
        )

    # ── Métodos abstractos (stubs) ────────────────────────────
    def connect(self) -> bool:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    def is_connected(self) -> bool:
        return self._connected

    def place_order(self, order: Order) -> Order:
        raise NotImplementedError

    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError

    def modify_order(self, order_id: str, quantity: Optional[int] = None,
                     limit_price: Optional[float] = None, stop_price: Optional[float] = None) -> bool:
        raise NotImplementedError

    def get_order(self, order_id: str) -> Optional[Order]:
        raise NotImplementedError

    def get_open_orders(self) -> list[Order]:
        raise NotImplementedError

    def get_positions(self) -> list[Position]:
        raise NotImplementedError

    def get_position(self, symbol: str, contract: str) -> Optional[Position]:
        raise NotImplementedError

    def get_fills(self, order_id: Optional[str] = None,
                  start: Optional[datetime] = None, end: Optional[datetime] = None) -> list[Fill]:
        raise NotImplementedError

    def get_account_summary(self) -> dict:
        raise NotImplementedError

    def sync(self) -> None:
        raise NotImplementedError