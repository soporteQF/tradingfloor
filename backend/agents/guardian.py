"""GUARDIAN AGENT — guardián único de riesgo y comportamiento.

Centraliza TODAS las reglas de riesgo (pre-trade, intra-trade, post-trade)
y reglas comportamentales. Es la última barrera antes de que una orden salga.

Responsabilidades:
1. Pre-trade guards (portfolio level): daily loss, trailing DD, max positions, correlation, consistency
2. Behavioral rules: max trades/hora, cooldown tras loss streak, kill-switch, max drawdown por estrategia
3. Drift detection: params live vs backtest (desde KG), performance decay
4. Emergency: kill switch global, flatten all, cancel all
5. Alertas a Chief (event bus)

Diseño: stateless en lo posible, estado en KG/Redis. El adapter (paper/live) tiene sus guards;
Guardian es capa superior de validación de negocio.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from agents.base import Agent
from agents.execution import Signal, SignalSide
from contracts import ErrorKind, ErrorNode, InsightNode
from knowledge_graph.client import KnowledgeGraph

log = logging.getLogger(__name__)


class GuardAction(str, Enum):
    ALLOW = "allow"
    WARN = "warn"       # permite pero alerta
    BLOCK = "block"     # rechaza orden
    REDUCE = "reduce"   # reduce tamaño
    FLATTEN = "flatten" # cierra posición
    KILL = "kill"       # emergency stop global


class GuardCategory(str, Enum):
    PRE_TRADE = "pre_trade"
    INTRA_TRADE = "intra_trade"
    POST_TRADE = "post_trade"
    BEHAVIORAL = "behavioral"
    DRIFT = "drift"
    EMERGENCY = "emergency"


@dataclass
class GuardResult:
    """Resultado de evaluar un guard."""
    action: GuardAction
    category: GuardCategory
    guard_name: str
    message: str
    severity: str = "info"  # info, warning, critical
    metadata: dict = field(default_factory=dict)

    @property
    def is_blocking(self) -> bool:
        return self.action in (GuardAction.BLOCK, GuardAction.FLATTEN, GuardAction.KILL)


@dataclass
class RiskLimits:
    """Límites de riesgo configurables (desde .env / Chief UI)."""
    # Daily loss
    max_daily_loss_usd: float = 1500.0
    # Trailing drawdown from peak
    max_trailing_dd_usd: float = 2500.0
    # Position limits
    max_contracts_per_symbol: int = 10
    max_total_contracts: int = 20
    max_notional_per_symbol: float = 100_000.0
    max_total_notional: float = 300_000.0
    # Correlation / concentration
    max_correlated_exposure: float = 0.7  # 70% en símbolos correlacionados
    # Behavioral
    max_trades_per_hour: int = 30
    max_trades_per_day: int = 100
    loss_streak_cooldown_trades: int = 3  # trades perdidos seguidos -> cooldown
    loss_streak_cooldown_minutes: int = 30
    # Drift
    max_param_drift_pct: float = 20.0
    min_trades_for_drift: int = 20
    # Emergency
    kill_switch_enabled: bool = True
    max_strategy_dd_pct: float = 15.0  # max DD por estrategia antes de flatten


@dataclass
class PortfolioState:
    """Estado actual del portfolio para evaluación de guards."""
    equity: float = 50_000.0
    peak_equity: float = 50_000.0
    daily_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    open_positions: dict = field(default_factory=dict)  # symbol -> {qty, notional, pnl}
    orders_today: int = 0
    trades_today: int = 0
    trades_last_hour: list = field(default_factory=list)  # timestamps
    loss_streak: int = 0
    last_trade_pnl: float = 0.0
    last_trade_time: Optional[datetime] = None


class GuardianAgent(Agent):
    name = "guardian"
    role = "Guardián único de riesgo y comportamiento. Última barrera antes de ejecutar."

    def __init__(self, kg: Optional[KnowledgeGraph] = None, limits: Optional[RiskLimits] = None):
        super().__init__(kg=kg)
        self.limits = limits or RiskLimits()
        self._portfolio = PortfolioState()
        self._lock = threading.RLock()
        self._kill_switch_active = False
        self._cooldown_until: Optional[datetime] = None
        self._strategy_dd: dict[str, float] = {}  # strategy_id -> max_dd_pct
        self._param_baselines: dict[str, dict] = {}  # strategy_id -> {param: value}

    # ── API Principal ─────────────────────────────────────────
    def check_pre_trade(self, signal: Signal, portfolio: PortfolioState) -> list[GuardResult]:
        """Evalúa todos los guards pre-trade. Returns lista de resultados."""
        with self._lock:
            self._update_portfolio(portfolio)
            results = []

            # Kill switch global
            if self._kill_switch_active:
                results.append(GuardResult(
                    action=GuardAction.KILL,
                    category=GuardCategory.EMERGENCY,
                    guard_name="global_kill_switch",
                    message="Kill switch activo — ninguna orden permitida",
                    severity="critical",
                ))
                return results

            # Cooldown por loss streak
            if self._cooldown_until and datetime.now(timezone.utc) < self._cooldown_until:
                remaining = (self._cooldown_until - datetime.now(timezone.utc)).total_seconds() / 60
                results.append(GuardResult(
                    action=GuardAction.BLOCK,
                    category=GuardCategory.BEHAVIORAL,
                    guard_name="loss_streak_cooldown",
                    message=f"Cooldown activo por loss streak: {remaining:.1f} min restantes",
                    severity="warning",
                ))
                return results

            # Daily loss limit
            daily_loss = -min(0, self._portfolio.daily_pnl)
            if daily_loss >= self.limits.max_daily_loss_usd:
                results.append(GuardResult(
                    action=GuardAction.FLATTEN,
                    category=GuardCategory.PRE_TRADE,
                    guard_name="daily_loss_limit",
                    message=f"Daily loss ${daily_loss:.0f} >= límite ${self.limits.max_daily_loss_usd:.0f} — FLATTEN ALL",
                    severity="critical",
                ))
                return results

            # Trailing drawdown
            current_dd = self._portfolio.peak_equity - self._portfolio.equity
            if current_dd >= self.limits.max_trailing_dd_usd:
                results.append(GuardResult(
                    action=GuardAction.FLATTEN,
                    category=GuardCategory.PRE_TRADE,
                    guard_name="trailing_drawdown",
                    message=f"Trailing DD ${current_dd:.0f} >= límite ${self.limits.max_trailing_dd_usd:.0f} — FLATTEN ALL",
                    severity="critical",
                ))
                return results

            # Max trades per hour
            now = datetime.now(timezone.utc)
            recent_trades = [t for t in self._portfolio.trades_last_hour if now - t < timedelta(hours=1)]
            if len(recent_trades) >= self.limits.max_trades_per_hour:
                results.append(GuardResult(
                    action=GuardAction.BLOCK,
                    category=GuardCategory.BEHAVIORAL,
                    guard_name="max_trades_per_hour",
                    message=f"Trades/hora {len(recent_trades)} >= límite {self.limits.max_trades_per_hour}",
                    severity="warning",
                ))

            # Max trades per day
            if self._portfolio.trades_today >= self.limits.max_trades_per_day:
                results.append(GuardResult(
                    action=GuardAction.BLOCK,
                    category=GuardCategory.BEHAVIORAL,
                    guard_name="max_trades_per_day",
                    message=f"Trades/día {self._portfolio.trades_today} >= límite {self.limits.max_trades_per_day}",
                    severity="warning",
                ))

            # Position limits por símbolo
            if signal.side in (SignalSide.LONG, SignalSide.SHORT):
                pos = self._portfolio.open_positions.get(signal.symbol, {})
                current_qty = pos.get("quantity", 0)
                current_notional = pos.get("notional", 0.0)
                new_qty = current_qty + (signal.quantity or 1)
                # Estimar notional nuevo (precio aprox)
                # TODO: usar precio real
                est_notional = abs(new_qty) * 20000 * 2  # aprox MNQ

                if abs(new_qty) > self.limits.max_contracts_per_symbol:
                    results.append(GuardResult(
                        action=GuardAction.REDUCE,
                        category=GuardCategory.PRE_TRADE,
                        guard_name="max_contracts_per_symbol",
                        message=f"Contratos {abs(new_qty)} > límite {self.limits.max_contracts_per_symbol} para {signal.symbol}",
                        severity="warning",
                        metadata={"max_allowed": self.limits.max_contracts_per_symbol},
                    ))

                if est_notional > self.limits.max_notional_per_symbol:
                    results.append(GuardResult(
                        action=GuardAction.REDUCE,
                        category=GuardCategory.PRE_TRADE,
                        guard_name="max_notional_per_symbol",
                        message=f"Notional estimado ${est_notional:,.0f} > límite ${self.limits.max_notional_per_symbol:,.0f}",
                        severity="warning",
                    ))

            # Total portfolio limits
            total_contracts = sum(abs(p.get("quantity", 0)) for p in self._portfolio.open_positions.values())
            total_notional = sum(abs(p.get("notional", 0)) for p in self._portfolio.open_positions.values())
            if total_contracts + (signal.quantity or 1) > self.limits.max_total_contracts:
                results.append(GuardResult(
                    action=GuardAction.BLOCK,
                    category=GuardCategory.PRE_TRADE,
                    guard_name="max_total_contracts",
                    message=f"Total contratos {total_contracts} >= límite {self.limits.max_total_contracts}",
                    severity="warning",
                ))

            # Correlation exposure (simplificado: NQ+ES+YM correlacionados)
            correlated = ["NQ", "ES", "YM"]
            if signal.symbol in correlated:
                corr_notional = sum(
                    abs(p.get("notional", 0)) for s, p in self._portfolio.open_positions.items()
                    if s in correlated
                )
                if corr_notional + est_notional > self.limits.max_correlated_exposure * self.limits.max_total_notional:
                    results.append(GuardResult(
                        action=GuardAction.REDUCE,
                        category=GuardCategory.PRE_TRADE,
                        guard_name="correlated_exposure",
                        message=f"Exposición correlacionada alta: ${corr_notional + est_notional:,.0f}",
                        severity="warning",
                    ))

            return results

    def check_intra_trade(self, portfolio: PortfolioState) -> list[GuardResult]:
        """Guards durante trade abierto (trailing DD por estrategia, etc.)."""
        with self._lock:
            self._update_portfolio(portfolio)
            results = []

            # Trailing DD por estrategia (desde KG)
            for strat_id, dd_pct in self._strategy_dd.items():
                if dd_pct >= self.limits.max_strategy_dd_pct:
                    results.append(GuardResult(
                        action=GuardAction.FLATTEN,
                        category=GuardCategory.INTRA_TRADE,
                        guard_name="strategy_max_dd",
                        message=f"Estrategia {strat_id} DD {dd_pct:.1f}% >= límite {self.limits.max_strategy_dd_pct}% — FLATTEN",
                        severity="critical",
                        metadata={"strategy_id": strat_id, "dd_pct": dd_pct},
                    ))

            return results

    def check_post_trade(self, trade_pnl: float, strategy_id: str = "") -> list[GuardResult]:
        """Actualiza estado post-trade: loss streak, cooldown, etc."""
        with self._lock:
            results = []
            self._portfolio.last_trade_pnl = trade_pnl
            self._portfolio.last_trade_time = datetime.now(timezone.utc)
            self._portfolio.trades_today += 1
            self._portfolio.trades_last_hour.append(self._portfolio.last_trade_time)

            # Loss streak tracking
            if trade_pnl < 0:
                self._portfolio.loss_streak += 1
                if self._portfolio.loss_streak >= self.limits.loss_streak_cooldown_trades:
                    self._cooldown_until = datetime.now(timezone.utc) + timedelta(
                        minutes=self.limits.loss_streak_cooldown_minutes
                    )
                    results.append(GuardResult(
                        action=GuardAction.BLOCK,
                        category=GuardCategory.BEHAVIORAL,
                        guard_name="loss_streak_cooldown_triggered",
                        message=f"Loss streak {self._portfolio.loss_streak} → cooldown {self.limits.loss_streak_cooldown_minutes} min",
                        severity="warning",
                    ))
            else:
                self._portfolio.loss_streak = 0

            # Drift detection (si hay trades suficientes)
            if strategy_id and self._portfolio.trades_today >= self.limits.min_trades_for_drift:
                drift_results = self._check_param_drift(strategy_id)
                results.extend(drift_results)

            return results

    def _check_param_drift(self, strategy_id: str) -> list[GuardResult]:
        """Compara params live vs baseline del backtest (desde KG)."""
        results = []
        if not self.kg or strategy_id not in self._param_baselines:
            return results

        # TODO: query real al KG para params actuales vs baseline
        # Placeholder: simula drift detection
        baseline = self._param_baselines[strategy_id]
        # En implementación real: obtener params actuales del strategy live
        # y comparar con baseline
        return results

    def set_strategy_dd(self, strategy_id: str, dd_pct: float) -> None:
        """Actualiza max drawdown por estrategia (llamado desde PaperLoop/ExecutionAgent)."""
        with self._lock:
            self._strategy_dd[strategy_id] = dd_pct

    def set_param_baseline(self, strategy_id: str, params: dict) -> None:
        """Registra baseline de parámetros del backtest (desde ValidationAgent)."""
        with self._lock:
            self._param_baselines[strategy_id] = params.copy()

    # ── Emergency Controls ────────────────────────────────────
    def activate_kill_switch(self, reason: str = "Manual activation") -> None:
        with self._lock:
            self._kill_switch_active = True
            log.critical("🛑 KILL SWITCH ACTIVADO: %s", reason)
            self._log_emergency("kill_switch_activated", reason)

    def deactivate_kill_switch(self) -> None:
        with self._lock:
            self._kill_switch_active = False
            log.warning("Kill switch DESACTIVADO")

    def is_kill_switch_active(self) -> bool:
        return self._kill_switch_active

    def emergency_flatten_all(self, execution_agent) -> list:
        """Cancela todas las órdenes y cierra todas las posiciones."""
        with self._lock:
            log.critical("🚨 EMERGENCY FLATTEN ALL")
            results = []
            # Cancel open orders
            for order in execution_agent.adapter.get_open_orders():
                execution_agent.adapter.cancel_order(order.id)
                results.append(f"Cancelled order {order.id}")
            # Flatten positions (enviar FLAT signals)
            for pos in execution_agent.get_open_positions():
                side = SignalSide.FLAT
                signal = Signal(
                    strategy_id="EMERGENCY",
                    symbol=pos.symbol,
                    contract=pos.contract,
                    side=side,
                    source_agent=self.name,
                )
                report = execution_agent.submit_signal(signal)
                results.append(f"Flatten {pos.symbol}: {report.status}")
            self._log_emergency("emergency_flatten", str(results))
            return results

    # ── Portfolio State Sync ──────────────────────────────────
    def _update_portfolio(self, portfolio: PortfolioState) -> None:
        self._portfolio.equity = portfolio.equity
        self._portfolio.peak_equity = max(self._portfolio.peak_equity, portfolio.equity)
        self._portfolio.daily_pnl = portfolio.daily_pnl
        self._portfolio.unrealized_pnl = portfolio.unrealized_pnl
        self._portfolio.realized_pnl = portfolio.realized_pnl
        self._portfolio.open_positions = portfolio.open_positions
        self._portfolio.trades_today = portfolio.trades_today
        self._portfolio.trades_last_hour = portfolio.trades_last_hour

    def update_portfolio(self, portfolio: PortfolioState) -> None:
        """API pública para sync desde PaperLoop/ExecutionAgent."""
        with self._lock:
            self._update_portfolio(portfolio)

    def get_portfolio_state(self) -> PortfolioState:
        with self._lock:
            return self._portfolio

    # ── Logging to KG ─────────────────────────────────────────
    def _log_emergency(self, event: str, detail: str) -> None:
        if not self.kg:
            return
        try:
            err = ErrorNode(
                kind=ErrorKind.RISK_BREACH,
                strategy_id=None,
                symbol=None,
                regime=None,
                root_cause=f"Guardian emergency: {event}",
                evidence={"event": event, "detail": detail},
            )
            self.kg.write_error(err)
        except Exception as e:
            log.error("Failed to log emergency to KG: %s", e)

    def log_guard_action(self, result: GuardResult, signal: Optional[Signal] = None) -> None:
        """Log guard action to KG for audit trail."""
        if not self.kg:
            return
        try:
            ins = InsightNode(
                kind=f"guard_{result.category.value}",
                description=f"{result.guard_name}: {result.message}",
                symbol=signal.symbol if signal else None,
                confidence=0.9 if result.severity == "critical" else 0.7,
                source_agent=self.name,
            )
            self.kg.write_insight(ins)
        except Exception as e:
            log.error("Failed to log guard action: %s", e)

    # ── Status para Chief UI ──────────────────────────────────
    def get_status(self) -> dict:
        with self._lock:
            return {
                "kill_switch": self._kill_switch_active,
                "cooldown_active": self._cooldown_until is not None and datetime.now(timezone.utc) < self._cooldown_until,
                "cooldown_until": self._cooldown_until.isoformat() if self._cooldown_until else None,
                "loss_streak": self._portfolio.loss_streak,
                "trades_today": self._portfolio.trades_today,
                "trades_last_hour": len([t for t in self._portfolio.trades_last_hour
                                        if datetime.now(timezone.utc) - t < timedelta(hours=1)]),
                "daily_pnl": self._portfolio.daily_pnl,
                "trailing_dd": self._portfolio.peak_equity - self._portfolio.equity,
                "open_positions": len(self._portfolio.open_positions),
                "strategy_dd": self._strategy_dd.copy(),
                "limits": {
                    "max_daily_loss": self.limits.max_daily_loss_usd,
                    "max_trailing_dd": self.limits.max_trailing_dd_usd,
                    "max_contracts_per_symbol": self.limits.max_contracts_per_symbol,
                    "max_total_contracts": self.limits.max_total_contracts,
                },
            }