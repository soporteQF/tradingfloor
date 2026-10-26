"""CHIEF OF STAFF — Orquestador central y interfaz de decisión humana.

Responsabilidades:
- Estado global: nightly loop, paper loop, guardian alerts
- Decisiones humanas: promote/retire strategies, kill switch, override
- Chat + Voice (Kokoro TTS) para comunicación con operador
- API para Chief UI (React panel lateral)
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Callable

from agents.base import Agent
from agents.guardian import GuardianAgent, GuardAction
from orchestration.event_bus import EventBus, STREAMS
from knowledge_graph.client import KnowledgeGraph

log = logging.getLogger(__name__)


class LoopState(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class StrategyState(str, Enum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    PAPER = "paper"
    LIVE = "live"
    RETIRED = "retired"
    REJECTED = "rejected"


@dataclass
class NightlyStatus:
    state: LoopState = LoopState.STOPPED
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    hypotheses_generated: int = 0
    hypotheses_passed: int = 0
    hypotheses_rejected: int = 0
    last_error: Optional[str] = None


@dataclass
class PaperStrategy:
    strategy_id: str
    name: str
    symbol: str
    timeframe: str
    regime: str
    state: StrategyState
    equity: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    trades_today: int = 0
    win_rate: float = 0.0
    avg_fill_slippage_bps: float = 0.0
    last_signal: Optional[str] = None
    last_fill: Optional[str] = None
    guard_alerts: list[str] = field(default_factory=list)


@dataclass
class GuardianAlert:
    timestamp: datetime
    guard_name: str
    action: GuardAction
    message: str
    severity: str
    strategy_id: Optional[str] = None
    symbol: Optional[str] = None


@dataclass
class ChiefCommand:
    """Comando desde Chief UI."""
    type: str  # "promote", "retire", "kill_switch", "pause_loop", "resume_loop", "override_guard"
    strategy_id: Optional[str] = None
    target_state: Optional[str] = None
    reason: str = ""
    user: str = "operator"


class ChiefOfStaff(Agent):
    name = "chief"
    role = "Orquestador central: nightly/paper loops, guardian alerts, decisiones humanas."

    def __init__(
        self,
        kg: KnowledgeGraph,
        event_bus: EventBus,
        guardian: GuardianAgent,
        nightly_loop_runner: Optional[Callable] = None,
        paper_loop_runner: Optional[Callable] = None,
        kokoro_tts: Optional[Callable] = None,
    ):
        super().__init__(kg=kg)
        self.event_bus = event_bus
        self.guardian = guardian
        self.nightly_loop_runner = nightly_loop_runner
        self.paper_loop_runner = paper_loop_runner
        self.kokoro_tts = kokoro_tts  # callable(text) -> audio bytes

        # Estado
        self.nightly_status = NightlyStatus()
        self.paper_strategies: dict[str, PaperStrategy] = {}
        self.guardian_alerts: list[GuardianAlert] = []
        self._cmd_queue: queue.Queue = queue.Queue()  # thread-safe
        self._lock = threading.RLock()

        # Loop de comandos
        self._running = False
        self._cmd_thread: Optional[threading.Thread] = None

        # Subscriptions
        self._subscribe_events()

    # ── Lifecycle ─────────────────────────────────────────────
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._cmd_thread = threading.Thread(target=self._command_loop, daemon=True)
        self._cmd_thread.start()
        log.info("ChiefOfStaff INICIADO")

    def stop(self) -> None:
        self._running = False
        if self._cmd_thread:
            self._cmd_thread.join(timeout=5)
        log.info("ChiefOfStaff DETENIDO")

    # ── Event Subscriptions ───────────────────────────────────
    def _subscribe_events(self) -> None:
        # Guardian alerts
        def on_guardian_alert(event):
            try:
                alert = GuardianAlert(
                    timestamp=datetime.fromisoformat(event.get("timestamp", datetime.now(timezone.utc).isoformat())),
                    guard_name=event.get("guard_name", "unknown"),
                    action=GuardAction(event.get("action", "warn")),
                    message=event.get("message", ""),
                    severity=event.get("severity", "warning"),
                    strategy_id=event.get("strategy_id"),
                    symbol=event.get("symbol"),
                )
                with self._lock:
                    self.guardian_alerts.append(alert)
                    # Mantener solo últimas 100
                    if len(self.guardian_alerts) > 100:
                        self.guardian_alerts = self.guardian_alerts[-100:]
                log.warning("🛡️ Guardian Alert: %s - %s", alert.guard_name, alert.message)
                self._speak(f"Guardian alert: {alert.guard_name}")
            except Exception as e:
                log.error("Error procesando guardian alert: %s", e)

        self.event_bus.subscribe("guardian_alerts", on_guardian_alert)

        # Paper trading events
        def on_paper_fill(event):
            try:
                strat_id = event.get("strategy_id")
                if strat_id and strat_id in self.paper_strategies:
                    with self._lock:
                        s = self.paper_strategies[strat_id]
                        s.realized_pnl = event.get("realized_pnl", s.realized_pnl)
                        s.unrealized_pnl = event.get("unrealized_pnl", s.unrealized_pnl)
                        s.trades_today = event.get("trades_today", s.trades_today)
                        s.win_rate = event.get("win_rate", s.win_rate)
                        s.avg_fill_slippage_bps = event.get("avg_slippage_bps", s.avg_fill_slippage_bps)
                        s.last_fill = f"{event.get('side')} {event.get('qty')} @ {event.get('price')}"
            except Exception as e:
                log.error("Error actualizando paper strategy: %s", e)

        self.event_bus.subscribe("paper_fills", on_paper_fill)

        def on_paper_signal(event):
            try:
                strat_id = event.get("strategy_id")
                if strat_id and strat_id in self.paper_strategies:
                    with self._lock:
                        self.paper_strategies[strat_id].last_signal = event.get("signal", "")
            except Exception as e:
                log.error("Error actualizando signal: %s", e)

        self.event_bus.subscribe("paper_signals", on_paper_signal)

    # ── Command Loop ──────────────────────────────────────────
    def _command_loop(self) -> None:
        while self._running:
            try:
                cmd = self._cmd_queue.get(timeout=1.0)
                self._execute_command(cmd)
            except queue.Empty:
                continue
            except Exception as e:
                log.error("Error en command loop: %s", e)

    def _execute_command(self, cmd: ChiefCommand) -> None:
        log.info("Chief ejecutando: %s %s", cmd.type, cmd.strategy_id or "")
        try:
            if cmd.type == "promote":
                self._promote_strategy(cmd)
            elif cmd.type == "retire":
                self._retire_strategy(cmd)
            elif cmd.type == "kill_switch":
                self._kill_switch(cmd)
            elif cmd.type == "pause_loop":
                self._pause_nightly(cmd)
            elif cmd.type == "resume_loop":
                self._resume_nightly(cmd)
            elif cmd.type == "override_guard":
                self._override_guard(cmd)
            elif cmd.type == "run_nightly_now":
                self._run_nightly_now(cmd)
        except Exception as e:
            log.error("Error ejecutando comando %s: %s", cmd.type, e)

    def _promote_strategy(self, cmd: ChiefCommand) -> None:
        if not cmd.strategy_id:
            return
        if self.kg:
            try:
                self.kg.conn.execute(
                    "MATCH (s:Strategy {id: $id}) SET s.status = $status",
                    {"id": cmd.strategy_id, "status": "paper"}
                )
            except Exception as e:
                log.error("Error promoviendo en KG: %s", e)

        with self._lock:
            if cmd.strategy_id in self.paper_strategies:
                self.paper_strategies[cmd.strategy_id].state = StrategyState.PAPER

        self._speak(f"Estrategia {cmd.strategy_id[:8]} promovida a paper trading")
        self.event_bus.publish("coordination", {
            "type": "strategy_promoted",
            "strategy_id": cmd.strategy_id,
            "reason": cmd.reason,
            "user": cmd.user,
        })

    def _retire_strategy(self, cmd: ChiefCommand) -> None:
        if not cmd.strategy_id:
            return
        if self.kg:
            try:
                self.kg.conn.execute(
                    "MATCH (s:Strategy {id: $id}) SET s.status = $status",
                    {"id": cmd.strategy_id, "status": "retired"}
                )
            except Exception as e:
                log.error("Error retirando en KG: %s", e)

        with self._lock:
            if cmd.strategy_id in self.paper_strategies:
                self.paper_strategies[cmd.strategy_id].state = StrategyState.RETIRED

        self._speak(f"Estrategia {cmd.strategy_id[:8]} retirada")
        self.event_bus.publish("coordination", {
            "type": "strategy_retired",
            "strategy_id": cmd.strategy_id,
            "reason": cmd.reason,
            "user": cmd.user,
        })

    def _kill_switch(self, cmd: ChiefCommand) -> None:
        self.guardian.activate_kill_switch(cmd.reason or "Manual kill switch by Chief")
        self._speak("Kill switch activado. Todas las posiciones se aplanarán.")
        self.event_bus.publish("coordination", {
            "type": "kill_switch_activated",
            "reason": cmd.reason,
            "user": cmd.user,
        })

    def _pause_nightly(self, cmd: ChiefCommand) -> None:
        self.nightly_status.state = LoopState.PAUSED
        self._speak("Nightly loop pausado")

    def _resume_nightly(self, cmd: ChiefCommand) -> None:
        self.nightly_status.state = LoopState.RUNNING
        self._speak("Nightly loop reanudado")

    def _override_guard(self, cmd: ChiefCommand) -> None:
        if cmd.strategy_id:
            self.guardian.override_guard(cmd.strategy_id, cmd.reason)
            self._speak(f"Guard override para {cmd.strategy_id[:8]}")

    def _run_nightly_now(self, cmd: ChiefCommand) -> None:
        if self.nightly_loop_runner:
            self.nightly_status.state = LoopState.RUNNING
            self._speak("Ejecutando nightly loop ahora")
            threading.Thread(target=self.nightly_loop_runner, daemon=True).start()

    # ── API Pública para Chief UI ─────────────────────────────
    def get_status(self) -> dict:
        with self._lock:
            return {
                "nightly": {
                    "state": self.nightly_status.state.value,
                    "last_run": self.nightly_status.last_run.isoformat() if self.nightly_status.last_run else None,
                    "next_run": self.nightly_status.next_run.isoformat() if self.nightly_status.next_run else None,
                    "hypotheses_generated": self.nightly_status.hypotheses_generated,
                    "hypotheses_passed": self.nightly_status.hypotheses_passed,
                    "hypotheses_rejected": self.nightly_status.hypotheses_rejected,
                    "last_error": self.nightly_status.last_error,
                },
                "paper_strategies": {
                    sid: {
                        "strategy_id": s.strategy_id,
                        "name": s.name,
                        "symbol": s.symbol,
                        "timeframe": s.timeframe,
                        "regime": s.regime,
                        "state": s.state.value,
                        "equity": s.equity,
                        "unrealized_pnl": s.unrealized_pnl,
                        "realized_pnl": s.realized_pnl,
                        "trades_today": s.trades_today,
                        "win_rate": s.win_rate,
                        "avg_fill_slippage_bps": s.avg_fill_slippage_bps,
                        "last_signal": s.last_signal,
                        "last_fill": s.last_fill,
                        "guard_alerts": s.guard_alerts,
                    }
                    for sid, s in self.paper_strategies.items()
                },
                "guardian_alerts": [
                    {
                        "timestamp": a.timestamp.isoformat(),
                        "guard_name": a.guard_name,
                        "action": a.action.value,
                        "message": a.message,
                        "severity": a.severity,
                        "strategy_id": a.strategy_id,
                        "symbol": a.symbol,
                    }
                    for a in self.guardian_alerts[-20:]  # últimas 20
                ],
                "guardian_status": self.guardian.get_status(),
            }

    def send_command(self, cmd: ChiefCommand) -> None:
        """Enqueue command from UI."""
        self._cmd_queue.put_nowait(cmd)

    def register_paper_strategy(self, strategy: PaperStrategy) -> None:
        with self._lock:
            self.paper_strategies[strategy.strategy_id] = strategy

    def update_nightly_status(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self.nightly_status, k):
                    setattr(self.nightly_status, k, v)

    # ── TTS Helper ────────────────────────────────────────────
    def _speak(self, text: str) -> None:
        if self.kokoro_tts:
            try:
                # Non-blocking
                threading.Thread(target=self.kokoro_tts, args=(text,), daemon=True).start()
            except Exception as e:
                log.warning("TTS failed: %s", e)


# ── Factory ────────────────────────────────────────────────────
def create_chief_of_staff(
    kg: KnowledgeGraph,
    event_bus: EventBus,
    guardian: GuardianAgent,
    nightly_loop_runner: Optional[Callable] = None,
    paper_loop_runner: Optional[Callable] = None,
    kokoro_tts: Optional[Callable] = None,
) -> ChiefOfStaff:
    return ChiefOfStaff(
        kg=kg,
        event_bus=event_bus,
        guardian=guardian,
        nightly_loop_runner=nightly_loop_runner,
        paper_loop_runner=paper_loop_runner,
        kokoro_tts=kokoro_tts,
    )


if __name__ == "__main__":
    # Test rápido
    import sys
    sys.path.insert(0, ".")
    from knowledge_graph.client import KnowledgeGraph
    from orchestration.event_bus import EventBus

    kg = KnowledgeGraph("./data/knowledge_graph/test_chief.db")
    kg._init_schema()
    eb = EventBus(enabled=False)
    guardian = GuardianAgent()
    chief = ChiefOfStaff(kg=kg, event_bus=eb, guardian=guardian)
    chief.start()

    # Registrar strategy de prueba
    from agents.chief import PaperStrategy, StrategyState
    chief.register_paper_strategy(PaperStrategy(
        strategy_id="test_123",
        name="ema_trend_nq_5m",
        symbol="NQ",
        timeframe="5m",
        regime="trend_up",
        state=StrategyState.PAPER,
        equity=50000,
        unrealized_pnl=120,
        realized_pnl=-50,
        trades_today=3,
        win_rate=0.67,
    ))

    # Simular comando
    chief.send_command(ChiefCommand(type="promote", strategy_id="test_123", reason="User approved"))
    time.sleep(0.5)

    status = chief.get_status()
    print(json.dumps(status, indent=2, default=str))

    chief.stop()
    kg.close()
    import shutil
    shutil.rmtree("./data/knowledge_graph/test_chief.db", ignore_errors=True)