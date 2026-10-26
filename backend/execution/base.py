"""Interfaz base de ejecución — idéntica para paper y live."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class Order:
    """Orden enviada al broker/simulador."""
    id: str = field(default_factory=lambda: f"ord_{uuid.uuid4().hex[:12]}")
    client_order_id: str = ""
    symbol: str = ""
    contract: str = ""          # p.ej. "MNQ" (micro) vs "NQ" (full)
    side: OrderSide = OrderSide.BUY
    type: OrderType = OrderType.MARKET
    quantity: int = 1
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "DAY"  # DAY, GTC, IOC, FOK
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    error_message: str = ""
    # Metadatos para trazabilidad
    strategy_id: str = ""
    signal_id: str = ""

    def is_open(self) -> bool:
        return self.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL)


@dataclass
class Fill:
    """Ejecución (fill) individual."""
    id: str = field(default_factory=lambda: f"fil_{uuid.uuid4().hex[:12]}")
    order_id: str = ""
    symbol: str = ""
    contract: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: int = 0
    price: float = 0.0
    commission: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Slippage real vs precio teórico
    slippage_ticks: float = 0.0
    liquidity_flag: str = ""  # "maker", "taker", "auction"


@dataclass
class Position:
    """Posición abierta agregada por símbolo/contrato."""
    symbol: str = ""
    contract: str = ""
    quantity: int = 0          # + long, - short
    avg_entry_price: float = 0.0
    mark_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    margin_used: float = 0.0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        return self.quantity < 0

    @property
    def is_flat(self) -> bool:
        return self.quantity == 0


class ExecutionAdapter(ABC):
    """Interfaz que el ExecutionAgent usa. Paper y Live la implementan igual."""

    @abstractmethod
    def connect(self) -> bool:
        """Conecta al broker/simulador. Returns True si OK."""

    @abstractmethod
    def disconnect(self) -> None:
        """Desconecta limpiamente."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Estado de conexión."""

    @abstractmethod
    def place_order(self, order: Order) -> Order:
        """Envía orden. Devuelve la orden con ID asignado y status actualizado."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancela orden por ID. Returns True si cancelada."""

    @abstractmethod
    def modify_order(self, order_id: str, quantity: Optional[int] = None,
                     limit_price: Optional[float] = None, stop_price: Optional[float] = None) -> bool:
        """Modifica orden viva."""

    @abstractmethod
    def get_order(self, order_id: str) -> Optional[Order]:
        """Consulta estado de orden."""

    @abstractmethod
    def get_open_orders(self) -> list[Order]:
        """Todas las órdenes abiertas."""

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Todas las posiciones actuales."""

    @abstractmethod
    def get_position(self, symbol: str, contract: str) -> Optional[Position]:
        """Posición específica."""

    @abstractmethod
    def get_fills(self, order_id: Optional[str] = None,
                  start: Optional[datetime] = None, end: Optional[datetime] = None) -> list[Fill]:
        """Historial de fills."""

    @abstractmethod
    def get_account_summary(self) -> dict:
        """Resumen de cuenta: equity, buying power, daily P&L, etc."""

    @abstractmethod
    def sync(self) -> None:
        """Sincroniza estado local con broker (live) o avanza simulación (paper)."""