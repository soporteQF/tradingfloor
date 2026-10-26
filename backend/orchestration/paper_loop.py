"""PAPER TRADING LOOP — corre estrategias validadas en modo shadow.

Flujo:
1. Carga StrategyDNA válidas del KG (status=VALIDATED o PAPER)
2. Para cada barra nueva (1m/5m/15m): genera Signal si setup activo
3. ExecutionAgent envía orden → PaperExecutionAdapter llena
4. Registra fills + quality metrics (slippage, latency, fill rate)
5. Guardian checks pre-trade (duplicados en adapter + agente)
6. Al cierre: daily report + A/B vs backtest expectancy

Integración con NightlyLoop:
- NightlyLoop produce StrategyDNA validados
- PaperLoop consume StrategyDNA y corre intradía
- Chief ve ambas en dashboard
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

from agents.execution import ExecutionAgent, Signal, SignalSide, SignalType
from agents.base import Agent
from contracts import StrategyDNA, StrategyStatus, Symbol, Timeframe
from execution import PaperExecutionAdapter
from knowledge_graph.client import KnowledgeGraph

log = logging.getLogger(__name__)


@dataclass
class PaperConfig:
    symbols: list[Symbol] = field(default_factory=lambda: ["NQ", "ES", "YM", "GC"])
    timeframes: list[Timeframe] = field(default_factory=lambda: ["1m", "5m", "15m"])
    starting_equity: float = 50_000.0
    slippage_ticks: dict[str, float] = field(default_factory=lambda: {
        "MNQ": 1.0, "MES": 1.0, "MYM": 1.0, "MGC": 1.0,
    })
    risk_limits: dict = field(default_factory=lambda: {
        "max_daily_loss": 1500.0,
        "max_trailing_dd": 2500.0,
        "max_contracts_per_symbol": 10,
        "consistency_rule_pct": 50,
    })
    data_provider = None  # callable(symbol, tf) -> DataFrame
    market_open: str = "09:30"    # ET
    market_close: str = "16:00"   # ET
    timezone: str = "America/New_York"


@dataclass
class PaperSession:
    """Sesión de paper trading para una estrategia."""
    strategy: StrategyDNA
    signal_count: int = 0
    fill_count: int = 0
    total_pnl: float = 0.0
    max_dd: float = 0.0
    start_equity: float = 0.0
    last_signal_time: Optional[datetime] = None


class PaperTradingLoop(Agent):
    name = "paper_loop"
    role = "Ejecuta estrategias validadas en paper, mide quality, reporta a Chief."

    def __init__(self, kg: KnowledgeGraph, config: PaperConfig):
        super().__init__(kg=kg)
        self.config = config

        # Adapter + Agent
        self.paper_adapter = PaperExecutionAdapter(
            starting_equity=config.starting_equity,
            slippage_ticks=config.slippage_ticks,
            data_provider=config.data_provider,
            risk_limits=config.risk_limits,
        )
        self.execution_agent = ExecutionAgent(self.paper_adapter, kg=kg)

        # Estado
        self._active_strategies: dict[str, PaperSession] = {}
        self._running = False
        self._last_bar_times: dict[tuple[str, Timeframe], datetime] = {}

    def start(self) -> None:
        """Inicia loop de paper trading."""
        if self._running:
            return
        self.paper_adapter.connect()
        self.execution_agent.connect()
        self._running = True
        self._load_validated_strategies()
        log.info("PaperTradingLoop INICIADO: %d estrategias activas", len(self._active_strategies))

    def stop(self) -> None:
        self._running = False
        self.execution_agent.disconnect()
        self.paper_adapter.disconnect()
        log.info("PaperTradingLoop DETENIDO")

    def _load_validated_strategies(self) -> None:
        """Carga StrategyDNA con status VALIDATED o PAPER del KG."""
        # TODO: query real al KG cuando tenga método get_strategies_by_status
        # Por ahora, placeholder - se llenará cuando Alpha Librarian exponga API
        log.info("Cargando estrategias validadas... (placeholder)")

    def register_strategy(self, dna: StrategyDNA) -> None:
        """Registra una estrategia para paper trading."""
        if dna.id in self._active_strategies:
            return
        session = PaperSession(
            strategy=dna,
            start_equity=self.paper_adapter.equity,
        )
        self._active_strategies[dna.id] = session
        log.info("Paper: registrada estrategia %s (%s %s %s+%s)",
                 dna.id[:12], dna.symbol, dna.timeframe, dna.entry.kind, dna.exit.kind)

    def on_bar(self, symbol: Symbol, timeframe: Timeframe, bar: dict) -> list:
        """Callback por cada barra nueva: genera señales si setup activo."""
        if not self._running:
            return []

        reports = []
        key = (symbol, timeframe)
        self._last_bar_times[key] = datetime.now(timezone.utc)

        # Para cada estrategia activa en este símbolo/timeframe
        for session in self._active_strategies.values():
            dna = session.strategy
            if dna.symbol != symbol or dna.timeframe != timeframe:
                continue
            if dna.status not in (StrategyStatus.VALIDATED, StrategyStatus.PAPER):
                continue

            # Generar señal si setup conditions met
            signal = self._check_setup(dna, bar)
            if signal:
                report = self.execution_agent.submit_signal(signal)
                session.signal_count += 1
                session.last_signal_time = signal.timestamp
                if report.fills:
                    session.fill_count += len(report.fills)
                    session.total_pnl += sum(f.price * f.quantity * (1 if f.side == SignalSide.LONG else -1) for f in report.fills)
                reports.append(report)

        # Sync execution agent (procesa trailing stops, time exits)
        sync_reports = self.execution_agent.sync()
        reports.extend(sync_reports)

        return reports

    def _check_setup(self, dna: StrategyDNA, bar: dict) -> Optional[Signal]:
        """Verifica si el setup de la estrategia se da en esta barra.

        Placeholder: lógica real vendrá de Regime Agent + Alpha Librarian.
        Por ahora: retorna None (no genera señales automáticas).
        """
        # TODO: implementar lógica de entry rules (EMA cross, donchian, etc.)
        # usando indicadores computados sobre barras recientes
        return None

    def force_signal(self, strategy_id: str, side: SignalSide,
                     signal_type: SignalType = SignalType.ENTRY) -> Optional[Signal]:
        """Fuerza una señal manual (para testing o Chief approval)."""
        session = self._active_strategies.get(strategy_id)
        if not session:
            return None
        dna = session.strategy
        signal = Signal(
            strategy_id=dna.id,
            symbol=dna.symbol,
            contract=dna.contract or "MNQ",
            side=side,
            signal_type=signal_type,
            source_agent=self.name,
        )
        report = self.execution_agent.submit_signal(signal)
        session.signal_count += 1
        return signal

    def get_session_stats(self, strategy_id: str) -> Optional[dict]:
        session = self._active_strategies.get(strategy_id)
        if not session:
            return None
        return {
            "strategy_id": strategy_id,
            "symbol": session.strategy.symbol,
            "timeframe": session.strategy.timeframe,
            "signals": session.signal_count,
            "fills": session.fill_count,
            "total_pnl": round(session.total_pnl, 2),
            "current_equity": self.paper_adapter.equity,
            "start_equity": session.start_equity,
        }

    def get_all_stats(self) -> dict:
        total_pnl = sum(s.total_pnl for s in self._active_strategies.values())
        return {
            "running": self._running,
            "active_strategies": len(self._active_strategies),
            "total_pnl": round(total_pnl, 2),
            "account": self.execution_agent.get_account_summary(),
            "sessions": {sid: self.get_session_stats(sid) for sid in self._active_strategies},
        }

    def daily_report(self) -> dict:
        """Reporte diario para Chief (18:00 ET)."""
        summary = self.get_all_stats()
        summary["timestamp"] = datetime.now(timezone.utc).isoformat()
        summary["date"] = datetime.now(timezone.utc).date().isoformat()
        # TODO: A/B vs backtest expectancy por estrategia
        return summary