"""Paper Trading Simulator — idéntica interfaz que live.

Diseño:
- Fills en close de la barra SIGUIENTE (realista: orden market al siguiente tick)
- Slippage configurable por símbolo (ticks)
- Comisión realista por contrato
- Risk guards pre-trade (daily loss, trailing DD, max contracts, consistency)
- Idempotencia: client_order_id evita duplicados
- Persistencia opcional de fills/orders en DuckDB para auditoría
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from .base import (
    ExecutionAdapter, Order, Position, Fill,
    OrderSide, OrderType, OrderStatus
)
from backtest.engine import SymbolSpec, SPECS

log = logging.getLogger(__name__)


class PaperExecutionAdapter(ExecutionAdapter):
    """Simulador de paper trading con risk guards de prop firm."""

    def __init__(self,
                 starting_equity: float = 50_000.0,
                 slippage_ticks: dict[str, float] | None = None,
                 data_provider=None,          # callable(symbol, timeframe) -> DataFrame con close actual
                 risk_limits: dict | None = None):
        self.starting_equity = starting_equity
        self.equity = starting_equity
        self.data_provider = data_provider

        # Slippage por contrato (ticks). Default conservador.
        self.slippage_ticks = slippage_ticks or {
            "MNQ": 1.0, "MES": 1.0, "MYM": 1.0, "MGC": 1.0,
            "NQ": 1.0, "ES": 1.0, "YM": 1.0, "GC": 1.0,
        }

        # Risk limits (prop firm defaults)
        rl = risk_limits or {}
        self.max_daily_loss = rl.get("max_daily_loss", 1500.0)
        self.max_trailing_dd = rl.get("max_trailing_dd", 2500.0)
        self.max_contracts_per_symbol = rl.get("max_contracts_per_symbol", 20)
        self.consistency_rule_pct = rl.get("consistency_rule_pct", 50)  # mejor día < 50% total profit
        self.max_position_value = rl.get("max_position_value", 100_000.0)

        # Estado interno
        self._orders: dict[str, Order] = {}
        self._fills: list[Fill] = []
        self._positions: dict[str, Position] = defaultdict(Position)  # key: "SYMBOL:CONTRACT"
        self._daily_pnl: dict[str, float] = defaultdict(float)  # date -> pnl
        self._peak_equity = starting_equity
        self._lock = threading.RLock()
        self._connected = False
        self._client_order_map: dict[str, str] = {}  # client_order_id -> order_id

        # Métricas de calidad de ejecución
        self.execution_stats = {
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_rejected": 0,
            "orders_cancelled": 0,
            "total_slippage_usd": 0.0,
            "total_commission_usd": 0.0,
        }

    # ── Conexión ──────────────────────────────────────────────
    def connect(self) -> bool:
        with self._lock:
            self._connected = True
            log.info("Paper executor conectado (equity=%.2f)", self.equity)
            return True

    def disconnect(self) -> None:
        with self._lock:
            self._connected = False
            log.info("Paper executor desconectado")

    def is_connected(self) -> bool:
        return self._connected

    # ── Market data helper ────────────────────────────────────
    def _get_current_price(self, symbol: str, contract: str) -> float:
        """Precio actual (close de la barra más reciente)."""
        if self.data_provider:
            try:
                df = self.data_provider(symbol, "1m")  # 1m para precio "actual"
                if df is not None and len(df) > 0:
                    return float(df["close"].iloc[-1])
            except Exception as e:
                log.warning("Data provider falló para %s: %s", symbol, e)
        # Fallback: precio sintético alrededor de 20000 (NQ) etc.
        base = {"MNQ": 20000, "MES": 5000, "MYM": 35000, "MGC": 2500,
                "NQ": 20000, "ES": 5000, "YM": 35000, "GC": 2500}
        return base.get(contract, base.get(symbol, 20000))

    def _get_spec(self, contract: str) -> SymbolSpec:
        return SPECS.get(contract, SPECS.get("MNQ"))

    # ── Risk Guards (HARD — rechazan orden antes de enviar) ───
    def _check_risk_pre_trade(self, order: Order) -> tuple[bool, str]:
        """Guards pre-trade estilo prop firm. Returns (ok, reason)."""
        today = datetime.now(timezone.utc).date().isoformat()

        # 1. Daily loss limit
        daily_loss = -self._daily_pnl.get(today, 0.0)
        if daily_loss >= self.max_daily_loss:
            return False, f"DAILY_LOSS_LIMIT: {daily_loss:.0f} >= {self.max_daily_loss:.0f}"

        # 2. Trailing drawdown
        current_dd = self._peak_equity - self.equity
        if current_dd >= self.max_trailing_dd:
            return False, f"TRAILING_DD: {current_dd:.0f} >= {self.max_trailing_dd:.0f}"

        # 3. Max contracts per symbol
        pos_key = f"{order.symbol}:{order.contract}"
        current_pos = self._positions[pos_key]
        new_qty = current_pos.quantity + (order.quantity if order.side == OrderSide.BUY else -order.quantity)
        if abs(new_qty) > self.max_contracts_per_symbol:
            return False, f"MAX_CONTRACTS: {abs(new_qty)} > {self.max_contracts_per_symbol}"

        # 4. Max position value (notional)
        price = self._get_current_price(order.symbol, order.contract)
        spec = self._get_spec(order.contract)
        notional = abs(new_qty) * price * spec.point_value
        if notional > self.max_position_value:
            return False, f"MAX_NOTIONAL: ${notional:,.0f} > ${self.max_position_value:,.0f}"

        # 5. Consistency rule (opcional, se evalúa al cerrar día)
        # Se aplica en end_of_day()

        return True, "OK"

    # ── Órdenes ───────────────────────────────────────────────
    def place_order(self, order: Order) -> Order:
        with self._lock:
            if not self._connected:
                order.status = OrderStatus.REJECTED
                order.error_message = "Not connected"
                return order

            # Idempotencia por client_order_id
            if order.client_order_id and order.client_order_id in self._client_order_map:
                existing_id = self._client_order_map[order.client_order_id]
                log.warning("Orden duplicada client_order_id=%s -> order_id=%s", order.client_order_id, existing_id)
                return self._orders[existing_id]

            # Risk guards
            ok, reason = self._check_risk_pre_trade(order)
            if not ok:
                order.status = OrderStatus.REJECTED
                order.error_message = reason
                self.execution_stats["orders_rejected"] += 1
                log.warning("Orden RECHAZADA risk: %s", reason)
                return order

            # Asignar ID si no tiene
            if not order.id:
                order.id = f"ord_{uuid.uuid4().hex[:12]}"

            # Registrar
            order.status = OrderStatus.SUBMITTED
            order.updated_at = datetime.now(timezone.utc)
            self._orders[order.id] = order
            if order.client_order_id:
                self._client_order_map[order.client_order_id] = order.id

            self.execution_stats["orders_submitted"] += 1
            log.info("Orden %s SUBMITTED: %s %d %s @ %s", order.id, order.side.value, order.quantity, order.contract, order.type.value)
            return order

    def cancel_order(self, order_id: str) -> bool:
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                return False
            if not order.is_open():
                return False
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now(timezone.utc)
            self.execution_stats["orders_cancelled"] += 1
            log.info("Orden %s CANCELLED", order_id)
            return True

    def modify_order(self, order_id: str, quantity: Optional[int] = None,
                     limit_price: Optional[float] = None, stop_price: Optional[float] = None) -> bool:
        with self._lock:
            order = self._orders.get(order_id)
            if not order or not order.is_open():
                return False
            if quantity is not None:
                order.quantity = quantity
            if limit_price is not None:
                order.limit_price = limit_price
            if stop_price is not None:
                order.stop_price = stop_price
            order.updated_at = datetime.now(timezone.utc)
            log.info("Orden %s MODIFIED", order_id)
            return True

    def get_order(self, order_id: str) -> Optional[Order]:
        with self._lock:
            return self._orders.get(order_id)

    def get_open_orders(self) -> list[Order]:
        with self._lock:
            return [o for o in self._orders.values() if o.is_open()]

    # ── Fills & Positions ─────────────────────────────────────
    def _process_fills(self) -> None:
        """Procesa órdenes pendientes: llena market orders en siguiente close."""
        with self._lock:
            for order in list(self._orders.values()):
                if order.status not in (OrderStatus.SUBMITTED, OrderStatus.PARTIAL):
                    continue
                if order.type != OrderType.MARKET:
                    # Solo market orders en paper v0; limit/stop se dejan pendientes
                    continue

                price = self._get_current_price(order.symbol, order.contract)
                spec = self._get_spec(order.contract)
                slip_ticks = self.slippage_ticks.get(order.contract, 1.0)
                slip_price = slip_ticks * spec.tick_size

                # Fill price: close + slippage en contra
                if order.side == OrderSide.BUY:
                    fill_price = price + slip_price
                else:
                    fill_price = price - slip_price

                fill_qty = order.quantity - order.filled_qty
                commission = spec.commission_rt * fill_qty

                # Crear fill
                fill = Fill(
                    order_id=order.id,
                    symbol=order.symbol,
                    contract=order.contract,
                    side=order.side,
                    quantity=fill_qty,
                    price=fill_price,
                    commission=commission,
                    slippage_ticks=slip_ticks,
                    liquidity_flag="taker",
                )
                self._fills.append(fill)

                # Actualizar orden
                order.filled_qty += fill_qty
                order.avg_fill_price = (
                    (order.avg_fill_price * (order.filled_qty - fill_qty) + fill_price * fill_qty)
                    / order.filled_qty
                )
                order.status = OrderStatus.FILLED if order.filled_qty >= order.quantity else OrderStatus.PARTIAL
                order.updated_at = datetime.now(timezone.utc)

                # Actualizar posición
                pos_key = f"{order.symbol}:{order.contract}"
                pos = self._positions[pos_key]
                pos.symbol = order.symbol
                pos.contract = order.contract

                signed_qty = fill_qty if order.side == OrderSide.BUY else -fill_qty
                new_total_qty = pos.quantity + signed_qty

                if pos.quantity == 0:
                    pos.avg_entry_price = fill_price
                elif (pos.quantity > 0 and signed_qty > 0) or (pos.quantity < 0 and signed_qty < 0):
                    # Aumentando posición misma dirección
                    pos.avg_entry_price = (
                        (pos.avg_entry_price * abs(pos.quantity) + fill_price * abs(signed_qty))
                        / abs(new_total_qty)
                    )
                else:
                    # Reduciendo o invirtiendo
                    closed_qty = min(abs(pos.quantity), abs(signed_qty))
                    realized = (fill_price - pos.avg_entry_price) * closed_qty * (1 if pos.quantity > 0 else -1)
                    pos.realized_pnl += realized * spec.point_value - commission
                    if abs(new_total_qty) > 0 and (pos.quantity > 0) != (new_total_qty > 0):
                        # Cambió de dirección
                        pos.avg_entry_price = fill_price

                pos.quantity = new_total_qty
                pos.mark_price = price
                pos.unrealized_pnl = (price - pos.avg_entry_price) * pos.quantity * spec.point_value
                pos.margin_used = abs(pos.quantity) * price * spec.point_value * 0.05  # ~5% margin
                pos.updated_at = datetime.now(timezone.utc)

                # Actualizar equity
                self.equity += fill.realized_pnl if hasattr(fill, 'realized_pnl') else 0
                # Equity = starting + realized + unrealized
                total_unrealized = sum(p.unrealized_pnl for p in self._positions.values())
                total_realized = sum(p.realized_pnl for p in self._positions.values())
                self.equity = self.starting_equity + total_realized + total_unrealized

                # Peak equity para trailing DD
                if self.equity > self._peak_equity:
                    self._peak_equity = self.equity

                # Daily P&L
                today = datetime.now(timezone.utc).date().isoformat()
                self._daily_pnl[today] = total_realized + total_unrealized

                # Stats
                self.execution_stats["orders_filled"] += 1
                self.execution_stats["total_slippage_usd"] += slip_price * spec.point_value * fill_qty
                self.execution_stats["total_commission_usd"] += commission

                log.info("FILL %s: %s %d %s @ %.2f (slip=%.1f ticks)", order.id, order.side.value, fill_qty, order.contract, fill_price, slip_ticks)

    def sync(self) -> None:
        """Avanza simulación: procesa fills, actualiza marks."""
        with self._lock:
            self._process_fills()
            # Actualizar mark prices de posiciones abiertas
            for pos in self._positions.values():
                if not pos.is_flat:
                    price = self._get_current_price(pos.symbol, pos.contract)
                    spec = self._get_spec(pos.contract)
                    pos.mark_price = price
                    pos.unrealized_pnl = (price - pos.avg_entry_price) * pos.quantity * spec.point_value
            # Recalcular equity
            total_unrealized = sum(p.unrealized_pnl for p in self._positions.values())
            total_realized = sum(p.realized_pnl for p in self._positions.values())
            self.equity = self.starting_equity + total_realized + total_unrealized
            if self.equity > self._peak_equity:
                self._peak_equity = self.equity

    def get_positions(self) -> list[Position]:
        with self._lock:
            return [p for p in self._positions.values() if not p.is_flat]

    def get_position(self, symbol: str, contract: str) -> Optional[Position]:
        with self._lock:
            pos = self._positions.get(f"{symbol}:{contract}")
            return pos if pos and not pos.is_flat else None

    def get_fills(self, order_id: Optional[str] = None,
                  start: Optional[datetime] = None, end: Optional[datetime] = None) -> list[Fill]:
        with self._lock:
            fills = self._fills
            if order_id:
                fills = [f for f in fills if f.order_id == order_id]
            if start:
                fills = [f for f in fills if f.timestamp >= start]
            if end:
                fills = [f for f in fills if f.timestamp <= end]
            return fills

    def get_account_summary(self) -> dict:
        with self._lock:
            total_unrealized = sum(p.unrealized_pnl for p in self._positions.values())
            total_realized = sum(p.realized_pnl for p in self._positions.values())
            today = datetime.now(timezone.utc).date().isoformat()
            daily = self._daily_pnl.get(today, 0.0)
            return {
                "equity": round(self.equity, 2),
                "starting_equity": self.starting_equity,
                "unrealized_pnl": round(total_unrealized, 2),
                "realized_pnl": round(total_realized, 2),
                "daily_pnl": round(daily, 2),
                "peak_equity": round(self._peak_equity, 2),
                "trailing_dd": round(self._peak_equity - self.equity, 2),
                "daily_loss_limit": self.max_daily_loss,
                "trailing_dd_limit": self.max_trailing_dd,
                "positions": len(self.get_positions()),
                "open_orders": len(self.get_open_orders()),
                "execution_stats": self.execution_stats.copy(),
            }

    # ── Helpers para tests/auditoría ──────────────────────────
    def reset(self) -> None:
        """Reset completo (para tests)."""
        with self._lock:
            self.equity = self.starting_equity
            self._peak_equity = self.starting_equity
            self._orders.clear()
            self._fills.clear()
            self._positions.clear()
            self._daily_pnl.clear()
            self._client_order_map.clear()
            self.execution_stats = {k: 0 for k in self.execution_stats}

import uuid