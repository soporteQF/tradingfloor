"""EL LOOP — Research propone, Validation mata, el grafo recuerda.

Este es el "sistema nervioso" del floor: el primer ciclo real donde dos
agentes colaboran con un árbitro y una memoria. Los otros 6 agentes se
enchufan a estos mismos contratos después.

Uso:
    python -m orchestration.loop --symbols NQ ES --timeframes 1h --max-per-symbol 20
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from agents.research import ResearchAgent
from agents.validation import ValidationAgent
from contracts import DailyReport, HypothesisOutcome, Symbol, Timeframe
from data_ingestion.store import DuckStore
from knowledge_graph.client import KnowledgeGraph
from orchestration.event_bus import EventBus
from validation.referee import Referee

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("loop")

SYMBOLS: list[Symbol] = ["NQ", "ES", "YM", "GC"]
TIMEFRAMES: list[Timeframe] = ["1h", "15m", "1d"]
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "./data/reports"))


class NightlyLoop:
    def __init__(self, store: DuckStore, kg: KnowledgeGraph, bus: EventBus | None = None):
        self.store = store
        self.kg = kg
        self.bus = bus or EventBus()
        self.research = ResearchAgent(kg=kg)
        self.validation = ValidationAgent(kg=kg, referee=Referee(n_folds=8))

    def run(self, symbols: list[Symbol], timeframes: list[Timeframe],
            max_per_symbol: int = 20) -> DailyReport:
        cycle_id = f"cyc_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}_{uuid4().hex[:4]}"
        log.info("=== CICLO %s ===", cycle_id)

        # 1. Datos disponibles (por par símbolo/timeframe)
        data = self._load_data(symbols, timeframes)
        if not data:
            log.error("No hay datos en DuckDB. Ejecuta primero: python -m data_ingestion.main")
            return DailyReport(cycle_id=cycle_id, data_quality_ok=False,
                               notes=["sin datos: ejecutar ingesta"])

        # 2. Research propone
        proposals = []
        for symbol in symbols:
            tfs = [tf for tf in timeframes if (symbol, tf) in data]
            for tf in tfs:
                proposals.extend(
                    self.research.propose([symbol], timeframe=tf, max_per_symbol=max_per_symbol)
                )
        log.info("research: %d hipótesis propuestas", len(proposals))
        if not proposals:
            return DailyReport(cycle_id=cycle_id, notes=["sin hipótesis nuevas (todo rechazado antes)"])

        # 3. Validation juzga (y escribe en el grafo)
        results = self.validation.validate_many(proposals, data)

        # 4. Reporte
        by_id = {h.id: h for h in proposals}
        outcomes = [
            HypothesisOutcome(
                hypothesis_id=r.hypothesis_id,
                symbol=by_id[r.hypothesis_id].symbol,
                entry_kind=by_id[r.hypothesis_id].entry.kind,
                exit_kind=by_id[r.hypothesis_id].exit.kind,
                passed=r.passed,
                sharpe=r.metrics.sharpe,
                max_drawdown=r.metrics.max_drawdown,
                trades=r.metrics.trades,
                reasons=r.failure_reasons,
            )
            for r in results
        ]

        report = DailyReport(
            cycle_id=cycle_id,
            proposals=len(proposals),
            validated=sum(1 for r in results if r.passed),
            rejected=sum(1 for r in results if not r.passed),
            winners=[r.hypothesis_id for r in results if r.passed],
            outcomes=outcomes,
            errors_logged=sum(1 for r in results if not r.passed),
            insights_logged=sum(1 for r in results if r.passed),
        )

        self._persist(report)
        self.bus.publish("coordination", {"type": "cycle_complete", "report": report.model_dump()})
        self._print_summary(report)
        return report

    # ── helpers ───────────────────────────────────────────
    def _load_data(self, symbols, timeframes) -> dict[tuple[str, str], "object"]:
        out = {}
        for symbol in symbols:
            for tf in timeframes:
                df = self.store.read_bars(symbol, tf)
                if df is not None and len(df) >= 400:
                    out[(symbol, tf)] = df
                    log.info("datos: %s %s → %d barras", symbol, tf, len(df))
                else:
                    log.warning("datos insuficientes: %s %s (%d)", symbol, tf, 0 if df is None else len(df))
        return out

    def _persist(self, report: DailyReport) -> None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path = REPORTS_DIR / f"{datetime.now(timezone.utc):%Y-%m-%d}_report.json"
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        log.info("reporte guardado: %s", path)

    def _print_summary(self, report: DailyReport) -> None:
        print("\n" + "=" * 74)
        print(f"  CICLO {report.cycle_id}")
        print("=" * 74)
        print(f"  propuestas={report.proposals}  pasan={report.validated}  mueren={report.rejected}")
        print(f"  errores escritos en grafo={report.errors_logged}  insights={report.insights_logged}")
        print("-" * 74)
        for o in report.outcomes[:15]:
            flag = "PASS" if o.passed else "FAIL"
            reasons = ",".join(o.reasons) if o.reasons else "-"
            print(f"  [{flag}] {o.symbol:>3} {o.entry_kind:<18} + {o.exit_kind:<15} "
                  f"sharpe={o.sharpe:>6.2f} dd={o.max_drawdown*100:>5.1f}% n={o.trades:<4} {reasons}")
        if len(report.outcomes) > 15:
            print(f"  ... +{len(report.outcomes) - 15} más")
        print("=" * 74 + "\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="NEXUS — ciclo nocturno Research→Validation")
    p.add_argument("--symbols", nargs="+", default=SYMBOLS, choices=SYMBOLS)
    p.add_argument("--timeframes", nargs="+", default=["1h"], choices=TIMEFRAMES)
    p.add_argument("--max-per-symbol", type=int, default=20)
    p.add_argument("--db", default=os.getenv("DUCKDB_PATH", "./data/processed/analytics.duckdb"))
    p.add_argument("--kg", default=os.getenv("KUZUDB_PATH", "./data/knowledge_graph/kuzu.db"))
    p.add_argument("--no-redis", action="store_true")
    args = p.parse_args(argv)

    store = DuckStore(args.db)
    kg = KnowledgeGraph(args.kg)
    bus = EventBus(enabled=not args.no_redis)

    loop = NightlyLoop(store=store, kg=kg, bus=bus)
    report = loop.run(args.symbols, args.timeframes, args.max_per_symbol)

    print("estado del grafo:", json.dumps(kg.stats(), indent=2))
    store.close()
    bus.close()
    return 0 if report.data_quality_ok else 2


if __name__ == "__main__":
    sys.exit(main())
