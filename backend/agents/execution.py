"""EXECUTION AGENT — ejecuta señales, gestiona órdenes, reporta fills.

Responsabilidades:
1. Recibe Signal (de Research/Validation/Regime) → convierte a Order
2. Risk check pre-trade (delega a adapter, pero valida reglas de negocio)
3. Envía orden → trackea fills → actualiza posición
4. Gestión de órdenes vivas: cancel/replace, time stops, trailing stops
5. Reporta fills + quality metrics al KG (ExecutionQuality Insight)
6. Idempotencia: client_order_id = signal_id

No decide QUÉ operar (eso es Research/Validation/Regime).
Solo decide CÓMO ejecutar (tipo orden, slicing, timing).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from agents.base import Agent
from execution import (
    ExecutionAdapter, Order, Position, Fill,
    OrderSide, OrderType, OrderStatus,
    PaperExecutionAdapter
)

log = logging.getLogger(__name__)


class SignalSide(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"      # cerrar posición
    REDUCE = "reduce"  # reducir posición X%


class SignalType(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    TIME_EXIT = "time_exit"
    REGIME_EXIT = "regime_exit"
    RISK_EXIT = "risk_exit"


@dataclass
class Signal:
    """Señal de trading normalizada (entrada estándar de todos los agentes)."""
    id: str = field(default_factory=lambda: f"sig_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    strategy_id: str = ""
    symbol: str = ""
    contract: str = ""          # p.ej. "MNQ"
    side: SignalSide = SignalSide.LONG
    signal_type: SignalType = SignalType.ENTRY
    quantity: Optional[int] = None      # None = calcular por sizing/riesgo
    target_price: Optional[float] = None
    stop_price: Optional[float] = None
    trailing_atr_mult: Optional[float] = None
    time_limit_bars: Optional[int] = None
    # Metadatos
    regime: str = ""
    confidence: float = 1.0
    source_agent: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class ExecutionReport:
    """Resultado de ejecutar una señal."""
    signal_id: str
    order_id: str
    status: OrderStatus
    fills: list[Fill] = field(default_factory=list)
    position_after: Optional[Position] = None
    error: str = ""
    latency_ms: float = 0.0


class ExecutionAgent(Agent):
    name = "execution"
    role = "Ejecuta señales con risk management, tracking de fills y quality metrics."

    def __init__(self, adapter: ExecutionAdapter, kg=None):
        super().__init__(kg=kg)
        self.adapter = adapter
        self._signal_queue: list[Signal] = []
        self._open_signals: dict[str, Signal] = {}  # signal_id -> Signal
        self._stops: dict[str, dict] = {}  # signal_id -> {stop_price, trailing, ...}

    def connect(self) -> bool:
        return self.adapter.connect()

    def disconnect(self) -> None:
        self.adapter.disconnect()

    # ── API principal ─────────────────────────────────────────
    def submit_signal(self, signal: Signal) -> ExecutionReport:
        """Punto de entrada único: recibe Signal, devuelve ExecutionReport."""
        start = datetime.now(timezone.utc)
        report = self._execute_signal(signal)
        report.latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        # Log al KG
        self._log_execution(report, signal)

        return report

    def submit_signals(self, signals: list[Signal]) -> list[ExecutionReport]:
        return [self.submit_signal(s) for s in signals]

    def cancel_signal(self, signal_id: str) -> bool:
        """Cancela orden asociada a signal_id."""
        if signal_id in self._open_signals:
            signal = self._open_signals[signal_id]
            # Buscar orden por client_order_id
            for order in self.adapter.get_open_orders():
                if order.client_order_id == signal_id:
                    return self.adapter.cancel_order(order.id)
        return False

    def sync(self) -> list[ExecutionReport]:
        """Sincroniza: procesa fills, actualiza trailing stops, time exits."""
        self.adapter.sync()
        reports = []
        # Verificar trailing stops / time exits
        for signal_id, stop_info in list(self._stops.items()):
            signal = self._open_signals.get(signal_id)
            if not signal:
                continue
            report = self._check_stop_conditions(signal, stop_info)
            if report:
                reports.append(report)
        return reports

    def get_open_positions(self) -> list[Position]:
        return self.adapter.get_positions()

    def get_account_summary(self) -> dict:
        return self.adapter.get_account_summary()

    # ── Lógica interna ────────────────────────────────────────
    def _execute_signal(self, signal: Signal) -> ExecutionReport:
        order = self._signal_to_order(signal)
        order.client_order_id = signal.id  # idempotencia
        order.strategy_id = signal.strategy_id
        order.signal_id = signal.id

        submitted = self.adapter.place_order(order)

        if submitted.status == OrderStatus.REJECTED:
            return ExecutionReport(
                signal_id=signal.id,
                order_id=submitted.id,
                status=OrderStatus.REJECTED,
                error=submitted.error_message,
            )

        self._open_signals[signal.id] = signal
        # Registrar stop/trailing si viene en señal
        if signal.stop_price or signal.trailing_atr_mult:
            self._stops[signal.id] = {
                "stop_price": signal.stop_price,
                "trailing_atr_mult": signal.trailing_atr_mult,
                "high_water": None,
                "low_water": None,
            }

        return ExecutionReport(
            signal_id=signal.id,
            order_id=submitted.id,
            status=submitted.status,
        )

    def _signal_to_order(self, signal: Signal) -> Order:
        """Convierte Signal normalizado a Order del adapter."""
        side_map = {
            SignalSide.LONG: OrderSide.BUY,
            SignalSide.SHORT: OrderSide.SELL,
            SignalSide.FLAT: OrderSide.SELL,  # se resuelve en _resolve_flat
            SignalSide.REDUCE: OrderSide.SELL,  # se resuelve en _resolve_reduce
        }

        # Resolver FLAT/REDUCE a side real según posición actual
        side = side_map[signal.side]
        pos = self.adapter.get_position(signal.symbol, signal.contract)

        if signal.side == SignalSide.FLAT:
            if pos and pos.is_long:
                side = OrderSide.SELL
            elif pos and pos.is_short:
                side = OrderSide.BUY
            else:
                return Order(  # sin posición → orden vacía que será rechazada
                    symbol=signal.symbol, contract=signal.contract,
                    side=OrderSide.BUY, quantity=0, status=OrderStatus.REJECTED,
                    error_message="FLAT signal but no open position"
                )

        if signal.side == SignalSide.REDUCE:
            if not pos or pos.is_flat:
                return Order(symbol=signal.symbol, contract=signal.contract,
                             side=OrderSide.BUY, quantity=0, status=OrderStatus.REJECTED,
                             error_message="REDUCE signal but no open position")
            reduce_qty = signal.quantity or max(1, abs(pos.quantity) // 2)
            side = OrderSide.SELL if pos.is_long else OrderSide.BUY
            qty = reduce_qty
        else:
            qty = signal.quantity or 1

        return Order(
            symbol=signal.symbol,
            contract=signal.contract,
            side=side,
            type=OrderType.MARKET,  # v0: solo market
            quantity=qty,
        )

    def _check_stop_conditions(self, signal: Signal, stop_info: dict) -> Optional[ExecutionReport]:
        """Verifica trailing stop / time exit / stop loss."""
        pos = self.adapter.get_position(signal.symbol, signal.contract)
        if not pos or pos.is_flat:
            # Posición cerrada → limpiar
            self._open_signals.pop(signal.id, None)
            self._stops.pop(signal.id, None)
            return None

        current_price = pos.mark_price
        action = None
        exit_type = ""

        # Trailing stop
        if stop_info.get("trailing_atr_mult"):
            atr = stop_info.get("atr", 1.0)  # TODO: pasar ATR real
            trail_dist = stop_info["trailing_atr_mult"] * atr
            if pos.is_long:
                if stop_info["high_water"] is None or current_price > stop_info["high_water"]:
                    stop_info["high_water"] = current_price
                trail_stop = stop_info["high_water"] - trail_dist
                if current_price <= trail_stop:
                    action = SignalSide.FLAT
                    exit_type = "trailing_stop"
            else:
                if stop_info["low_water"] is None or current_price < stop_info["low_water"]:
                    stop_info["low_water"] = current_price
                trail_stop = stop_info["low_water"] + trail_dist
                if current_price >= trail_stop:
                    action = SignalSide.FLAT
                    exit_type = "trailing_stop"

        # Stop loss fijo
        if not action and stop_info.get("stop_price"):
            stop_px = stop_info["stop_price"]
            if pos.is_long and current_price <= stop_px:
                action = SignalSide.FLAT
                exit_type = "stop_loss"
            elif pos.is_short and current_price >= stop_px:
                action = SignalSide.FLAT
                exit_type = "stop_loss"

        # Time exit
        if not action and signal.time_limit_bars:
            # TODO: trackear barras desde entrada
            pass

        if action:
            exit_signal = Signal(
                id=f"{signal.id}_exit",
                strategy_id=signal.strategy_id,
                symbol=signal.symbol,
                contract=signal.contract,
                side=action,
                signal_type=SignalType(exit_type),
                source_agent=self.name,
            )
            return self.submit_signal(exit_signal)

        return None

    def _log_execution(self, report: ExecutionReport, signal: Signal) -> None:
        """Escribe métricas de calidad de ejecución al KG."""
        if not self.kg:
            return

        # TODO: escribir InsightNode tipo "execution_quality" con slippage, fill rate, latency
        # Por ahora solo log
        if report.fills:
            total_slip = sum(f.slippage_ticks for f in report.fills)
            avg_slip = total_slip / len(report.fills)
            log.info("[%s] EXEC quality: signal=%s fills=%d avg_slip=%.2f ticks",
                     self.name, signal.id, len(report.fills), avg_slip)