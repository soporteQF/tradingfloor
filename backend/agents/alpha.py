"""ALPHA LIBRARIAN — Knowledge Graph query engine & playbook generator.

Consulta el KG y responde:
- "¿Qué setups funcionaron en range_low_vol NQ 15m?"
- "Playbook para trend_up GC: entry/exit típicos, sizing, risk"
- "Causal path: Error(overfit) → Insight(param_stability) → StrategyDNA"
- "Drift report: estrategia X params vs baseline"

Usa KuzuDB (Cypher) para traversals, NO LLM — determinístico, rápido, auditable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from agents.base import Agent
from knowledge_graph.client import KnowledgeGraph

log = logging.getLogger(__name__)


class QueryType(str, Enum):
    PLAYBOOK = "playbook"
    CAUSAL_PATH = "causal_path"
    DRIFT_REPORT = "drift_report"
    REGIME_STATS = "regime_stats"
    STRATEGY_PERFORMANCE = "strategy_performance"
    ERROR_ANALYSIS = "error_analysis"
    INSIGHT_LOOKUP = "insight_lookup"


@dataclass
class PlaybookEntry:
    """Entrada individual en un playbook."""
    strategy_id: str
    hypothesis_id: str
    symbol: str
    timeframe: str
    entry_kind: str
    exit_kind: str
    status: str
    sharpe: float
    max_dd: float
    n_trades: int
    fingerprint: str


@dataclass
class CausalPath:
    """Ruta causal Error → Insight → Strategy."""
    error_kind: str
    error_root_cause: str
    insight_kind: str
    insight_description: str
    strategy_id: str
    prevented: bool


@dataclass
class DriftReport:
    """Reporte de drift de parámetros vs baseline."""
    strategy_id: str
    param_name: str
    baseline_value: float
    current_value: float
    drift_pct: float
    is_significant: bool
    recommendation: str


@dataclass
class RegimeStats:
    """Estadísticas de performance por régimen (usa HypothesisRecord)."""
    entry_kind: str
    exit_kind: str
    symbol: str
    timeframe: str
    n_hypotheses: int
    avg_sharpe: float
    passed_count: int
    failed_count: int


@dataclass
class AlphaQuery:
    """Consulta estructurada al Alpha Librarian."""
    query_type: QueryType
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    regime: Optional[str] = None
    strategy_id: Optional[str] = None
    lookback_days: int = 90
    min_sharpe: float = 0.5
    max_dd: float = 0.2


@dataclass
class AlphaResult:
    """Resultado de una consulta."""
    query: AlphaQuery
    timestamp: datetime
    playbook: list[PlaybookEntry] = field(default_factory=list)
    causal_paths: list[CausalPath] = field(default_factory=list)
    drift_reports: list[DriftReport] = field(default_factory=list)
    regime_stats: list[RegimeStats] = field(default_factory=list)
    strategy_performance: list[dict] = field(default_factory=list)
    error_analysis: list[dict] = field(default_factory=list)
    insights: list[dict] = field(default_factory=list)
    summary: str = ""


class AlphaLibrarian(Agent):
    name = "alpha"
    role = "Consulta Knowledge Graph: playbooks, causal paths, drift reports, regime stats."

    def __init__(
        self,
        kg: KnowledgeGraph,
        event_bus=None,
        min_sharpe_threshold: float = 0.5,
        max_dd_threshold: float = 0.2,
    ):
        super().__init__(kg=kg)
        self.event_bus = event_bus
        self.min_sharpe_threshold = min_sharpe_threshold
        self.max_dd_threshold = max_dd_threshold

    # ── API Pública ─────────────────────────────────────────────
    def query(self, q: AlphaQuery) -> AlphaResult:
        """Ejecuta consulta según tipo."""
        log.info("AlphaLibrarian: %s %s %s %s", q.query_type, q.symbol, q.timeframe, q.regime)

        result = AlphaResult(query=q, timestamp=datetime.now(timezone.utc))

        if q.query_type == QueryType.PLAYBOOK:
            result.playbook = self._build_playbook(q)
            result.summary = self._summarize_playbook(result.playbook)

        elif q.query_type == QueryType.CAUSAL_PATH:
            result.causal_paths = self._find_causal_paths(q)
            result.summary = self._summarize_causal(result.causal_paths)

        elif q.query_type == QueryType.DRIFT_REPORT:
            result.drift_reports = self._drift_report(q)
            result.summary = self._summarize_drift(result.drift_reports)

        elif q.query_type == QueryType.REGIME_STATS:
            result.regime_stats = self._regime_stats(q)
            result.summary = self._summarize_regime_stats(result.regime_stats)

        elif q.query_type == QueryType.STRATEGY_PERFORMANCE:
            result.strategy_performance = self._strategy_performance(q)
            result.summary = self._summarize_perf(result.strategy_performance)

        elif q.query_type == QueryType.ERROR_ANALYSIS:
            result.error_analysis = self._error_analysis(q)
            result.summary = self._summarize_errors(result.error_analysis)

        elif q.query_type == QueryType.INSIGHT_LOOKUP:
            result.insights = self._insight_lookup(q)
            result.summary = self._summarize_insights(result.insights)

        # Log a KG
        if self.kg:
            try:
                from contracts import InsightNode
                ins = InsightNode(
                    kind="alpha_query",
                    description=f"{q.query_type.value}: {q.symbol or 'ALL'} {q.timeframe or ''} {q.regime or ''} → {len(result.playbook or result.causal_paths or result.drift_reports or result.regime_stats or result.strategy_performance or result.error_analysis or result.insights)} results",
                    symbol=q.symbol or "ALL",
                    confidence=0.9,
                    source_agent=self.name,
                    metadata={"query_type": q.query_type.value, "result_count": len(result.playbook or result.causal_paths or result.drift_reports or result.regime_stats or result.strategy_performance or result.error_analysis or result.insights)},
                )
                self.kg.write_insight(ins)
            except Exception:
                pass

        return result

    # ── Playbook ────────────────────────────────────────────────
    def _build_playbook(self, q: AlphaQuery) -> list[PlaybookEntry]:
        """Construye playbook: estrategias validadas por símbolo/timeframe."""
        where = []
        params = {}

        if q.symbol:
            where.append("s.symbol = $symbol")
            params["symbol"] = q.symbol
        if q.timeframe:
            where.append("s.timeframe = $tf")
            params["tf"] = q.timeframe

        where.append("s.sharpe >= $min_sharpe")
        where.append("s.max_drawdown <= $max_dd")
        params["min_sharpe"] = q.min_sharpe
        params["max_dd"] = q.max_dd

        where_clause = " AND ".join(where)

        cypher = f"""
        MATCH (s:Strategy)
        WHERE {where_clause}
        RETURN s.id as id, s.hypothesis_id as hypothesis_id, s.symbol as symbol, s.timeframe as timeframe,
               s.entry_kind as entry_kind, s.exit_kind as exit_kind,
               s.status as status, s.sharpe as sharpe, s.max_drawdown as max_drawdown,
               s.trades as trades, s.fingerprint as fingerprint
        ORDER BY s.sharpe DESC
        LIMIT 20
        """

        rows = self.kg.query(cypher, params)
        entries = []
        for r in rows:
            entries.append(PlaybookEntry(
                strategy_id=r["id"],
                hypothesis_id=r["hypothesis_id"],
                symbol=r["symbol"],
                timeframe=r["timeframe"],
                entry_kind=r["entry_kind"],
                exit_kind=r["exit_kind"],
                status=r["status"],
                sharpe=r["sharpe"],
                max_dd=r["max_drawdown"],
                n_trades=r["trades"],
                fingerprint=r["fingerprint"],
            ))
        return entries

    # ── Causal Path ─────────────────────────────────────────────
    def _find_causal_paths(self, q: AlphaQuery) -> list[CausalPath]:
        """Error → Insight → Strategy (prevención)."""
        where = []
        params = {}
        if q.symbol:
            where.append("e.symbol = $symbol")
            params["symbol"] = q.symbol
        if q.lookback_days:
            where.append("e.created_at >= $since")
            params["since"] = (datetime.now(timezone.utc) - timedelta(days=q.lookback_days)).isoformat()

        where_clause = " AND ".join(where) if where else "1=1"

        cypher = f"""
        MATCH (e:Error)
        WHERE {where_clause}
        OPTIONAL MATCH (e)-[:CAUSES]->(i:Insight)
        OPTIONAL MATCH (s:Strategy) WHERE s.hypothesis_id = i.note
        RETURN e.kind as error_kind, e.root_cause as error_root_cause,
               i.kind as insight_kind, i.note as insight_note,
               s.id as strategy_id,
               CASE WHEN i.id IS NOT NULL THEN true ELSE false END as prevented
        ORDER BY e.created_at DESC
        LIMIT 50
        """

        rows = self.kg.query(cypher, params)
        paths = []
        for r in rows:
            paths.append(CausalPath(
                error_kind=r["error_kind"],
                error_root_cause=r["error_root_cause"],
                insight_kind=r["insight_kind"] if r["insight_kind"] else "N/A",
                insight_description=r["insight_note"] if r["insight_note"] else "N/A",
                strategy_id=r["strategy_id"] if r["strategy_id"] else "N/A",
                prevented=r["prevented"],
            ))
        return paths

    # ── Drift Report ────────────────────────────────────────────
    def _drift_report(self, q: AlphaQuery) -> list[DriftReport]:
        """Compara params actuales vs baseline (requiere StrategyDNA con params/baseline_params en metadata).
        
        Nota: El KG actual solo guarda entry_kind, exit_kind, fingerprint. Para drift completo
        se necesitaría almacenar params y baseline_params en el nodo Strategy o en metadata.
        """
        if not q.strategy_id:
            return []

        # Por ahora retorna vacío - se implementaría cuando se guarden params en KG
        return []

    # ── Regime Stats (via HypothesisRecord) ────────────────────
    def _regime_stats(self, q: AlphaQuery) -> list[RegimeStats]:
        """Stats agregadas por entry/exit kind (proxy de régimen)."""
        where = []
        params = {}
        if q.symbol:
            where.append("h.symbol = $symbol")
            params["symbol"] = q.symbol
        if q.timeframe:
            where.append("h.timeframe = $tf")
            params["tf"] = q.timeframe

        where_clause = " AND ".join(where) if where else "1=1"

        cypher = f"""
        MATCH (h:HypothesisRecord)
        WHERE {where_clause}
        WITH h.entry_kind as entry_kind, h.exit_kind as exit_kind, h.symbol as symbol, h.timeframe as tf,
             count(h) as n_hyp, avg(h.sharpe) as avg_sharpe,
             sum(CASE WHEN h.passed = true THEN 1 ELSE 0 END) as passed,
             sum(CASE WHEN h.passed = false THEN 1 ELSE 0 END) as failed
        RETURN entry_kind, exit_kind, symbol, tf, n_hyp, avg_sharpe, passed, failed
        ORDER BY avg_sharpe DESC
        """

        rows = self.kg.query(cypher, params)
        stats = []
        for r in rows:
            stats.append(RegimeStats(
                entry_kind=r["entry_kind"],
                exit_kind=r["exit_kind"],
                symbol=r["symbol"],
                timeframe=r["tf"],
                n_hypotheses=r["n_hyp"],
                avg_sharpe=r["avg_sharpe"],
                passed_count=r["passed"],
                failed_count=r["failed"],
            ))
        return stats

    # ── Strategy Performance ────────────────────────────────────
    def _strategy_performance(self, q: AlphaQuery) -> list[dict]:
        """Performance detallada de estrategias validadas."""
        where = []
        params = {}
        if q.symbol:
            where.append("s.symbol = $symbol")
            params["symbol"] = q.symbol
        if q.strategy_id:
            where.append("s.id = $strategy_id")
            params["strategy_id"] = q.strategy_id

        where_clause = " AND ".join(where) if where else "1=1"

        cypher = f"""
        MATCH (s:Strategy)
        WHERE {where_clause}
        RETURN s.id as id, s.hypothesis_id as hypothesis_id, s.symbol as symbol, s.timeframe as timeframe,
               s.entry_kind as entry_kind, s.exit_kind as exit_kind,
               s.status as status, s.sharpe as sharpe, s.max_drawdown as max_drawdown,
               s.trades as trades, s.fingerprint as fingerprint, s.created_at as created_at
        ORDER BY s.sharpe DESC
        LIMIT 50
        """

        return self.kg.query(cypher, params)

    # ── Error Analysis ──────────────────────────────────────────
    def _error_analysis(self, q: AlphaQuery) -> list[dict]:
        """Errores frecuentes por kind/símbolo."""
        where = []
        params = {}
        if q.symbol:
            where.append("e.symbol = $symbol")
            params["symbol"] = q.symbol
        if q.lookback_days:
            where.append("e.created_at >= $since")
            params["since"] = (datetime.now(timezone.utc) - timedelta(days=q.lookback_days)).isoformat()

        where_clause = " AND ".join(where) if where else "1=1"

        cypher = f"""
        MATCH (e:Error)
        WHERE {where_clause}
        RETURN e.kind as kind, count(*) as count, e.symbol as symbol, e.regime as regime,
               collect(e.root_cause) as samples
        ORDER BY count DESC
        LIMIT 20
        """

        return self.kg.query(cypher, params)

    # ── Insight Lookup ──────────────────────────────────────────
    def _insight_lookup(self, q: AlphaQuery) -> list[dict]:
        """Insights por kind/símbolo."""
        where = []
        params = {}
        if q.symbol:
            where.append("i.symbol = $symbol")
            params["symbol"] = q.symbol

        where_clause = " AND ".join(where) if where else "1=1"

        cypher = f"""
        MATCH (i:Insight)
        WHERE {where_clause}
        RETURN i.kind as kind, i.note as note, i.symbol as symbol, i.regime as regime,
               i.confidence as confidence, i.source_agent as source_agent, i.created_at as created_at
        ORDER BY i.created_at DESC
        LIMIT 50
        """

        return self.kg.query(cypher, params)

    # ── Summaries (para Chief UI) ───────────────────────────────
    def _summarize_playbook(self, entries: list[PlaybookEntry]) -> str:
        if not entries:
            return "No hay estrategias validadas para esos criterios."
        top = entries[0]
        return f"Playbook: {len(entries)} estrategias. Top: {top.entry_kind}+{top.exit_kind} {top.symbol} {top.timeframe} Sharpe={top.sharpe:.2f} DD={top.max_dd:.1%}"

    def _summarize_causal(self, paths: list[CausalPath]) -> str:
        if not paths:
            return "Sin rutas causales."
        prevented = sum(1 for p in paths if p.prevented)
        return f"Rutas causales: {len(paths)} total, {prevented} con insight preventivo."

    def _summarize_drift(self, reports: list[DriftReport]) -> str:
        if not reports:
            return "Sin drift detectado (params no almacenados en KG actual)."
        sig = sum(1 for r in reports if r.is_significant)
        return f"Drift report: {len(reports)} params, {sig} significativos (>20%)."

    def _summarize_regime_stats(self, stats: list[RegimeStats]) -> str:
        if not stats:
            return "Sin datos por entry/exit kind."
        best = max(stats, key=lambda s: s.avg_sharpe)
        return f"Combo top: {best.entry_kind}+{best.exit_kind} {best.symbol} {best.timeframe} avg_sharpe={best.avg_sharpe:.2f}"

    def _summarize_perf(self, perfs: list[dict]) -> str:
        if not perfs:
            return "Sin performance data."
        return f"{len(perfs)} estrategias. Top sharpe: {perfs[0].get('sharpe', 0):.2f}"

    def _summarize_errors(self, errors: list[dict]) -> str:
        if not errors:
            return "Sin errores."
        top = errors[0]
        return f"Error top: {top.get('e.kind', 'N/A')} ({top.get('count', 0)} ocurrencias)"

    def _summarize_insights(self, insights: list[dict]) -> str:
        if not insights:
            return "Sin insights."
        return f"{len(insights)} insights. Último: {insights[0].get('i.kind', 'N/A')}"


# ── Factory & Helpers ───────────────────────────────────────────
def create_alpha_librarian(
    kg: KnowledgeGraph,
    event_bus=None,
    min_sharpe: float = 0.5,
    max_dd: float = 0.2,
) -> AlphaLibrarian:
    return AlphaLibrarian(
        kg=kg,
        event_bus=event_bus,
        min_sharpe_threshold=min_sharpe,
        max_dd_threshold=max_dd,
    )


def query_playbook(
    kg: KnowledgeGraph,
    symbol: str = None,
    timeframe: str = None,
    regime: str = None,
    min_sharpe: float = 0.5,
    max_dd: float = 0.2,
) -> AlphaResult:
    """Helper one-liner para Chief/UI."""
    q = AlphaQuery(
        query_type=QueryType.PLAYBOOK,
        symbol=symbol,
        timeframe=timeframe,
        regime=regime,
        min_sharpe=min_sharpe,
        max_dd=max_dd,
    )
    agent = AlphaLibrarian(kg=kg)
    return agent.query(q)


def query_causal(
    kg: KnowledgeGraph,
    symbol: str = None,
    lookback_days: int = 90,
) -> AlphaResult:
    q = AlphaQuery(query_type=QueryType.CAUSAL_PATH, symbol=symbol, lookback_days=lookback_days)
    agent = AlphaLibrarian(kg=kg)
    return agent.query(q)


def query_drift(kg: KnowledgeGraph, strategy_id: str) -> AlphaResult:
    q = AlphaQuery(query_type=QueryType.DRIFT_REPORT, strategy_id=strategy_id)
    agent = AlphaLibrarian(kg=kg)
    return agent.query(q)


def query_regime_stats(
    kg: KnowledgeGraph,
    symbol: str = None,
    timeframe: str = None,
    regime: str = None,
) -> AlphaResult:
    q = AlphaQuery(query_type=QueryType.REGIME_STATS, symbol=symbol, timeframe=timeframe, regime=regime)
    agent = AlphaLibrarian(kg=kg)
    return agent.query(q)


if __name__ == "__main__":
    # Test rápido
    import sys
    sys.path.insert(0, ".")
    from knowledge_graph.client import KnowledgeGraph
    from contracts import StrategyDNA, ErrorNode, InsightNode, EntryRule, ExitRule, SizingRule, ValidationMetrics, StrategyStatus
    import uuid

    kg = KnowledgeGraph("./data/knowledge_graph/test_alpha_kuzu.db")
    kg._init_schema()

    # Poblar datos de prueba
    s = StrategyDNA(
        id=str(uuid.uuid4()),
        hypothesis_id="h1",
        symbol="NQ",
        timeframe="5m",
        entry=EntryRule(kind="ema_cross", params={"ema_fast": 9, "ema_slow": 21}),
        exit=ExitRule(kind="atr_trailing", params={"atr_mult": 2.0}),
        sizing=SizingRule(kind="fixed_contracts", params={"contracts": 1}),
        regime_gates=["trend_up"],
        performance=ValidationMetrics(sharpe=1.8, max_drawdown=0.12, trades=150),
        fingerprint="ema_cross|atr_trailing|NQ|5m|trend_up",
        status=StrategyStatus.VALIDATED,
    )
    kg.write_strategy(s)

    # Test queries
    agent = AlphaLibrarian(kg=kg)

    # Playbook
    res = agent.query(AlphaQuery(query_type=QueryType.PLAYBOOK, symbol="NQ", timeframe="5m"))
    print("PLAYBOOK:", res.summary)
    for p in res.playbook:
        print(f"  {p.strategy_id[:8]} {p.entry_kind}+{p.exit_kind} sharpe={p.sharpe:.2f} dd={p.max_dd:.1%}")

    # Regime stats
    res = agent.query(AlphaQuery(query_type=QueryType.REGIME_STATS, symbol="NQ"))
    print("\nREGIME STATS:", res.summary)
    for r in res.regime_stats:
        print(f"  {r.entry_kind}+{r.exit_kind} n={r.n_hypotheses} passed={r.passed_count} avg_sharpe={r.avg_sharpe:.2f}")

    kg.close()
    import shutil
    shutil.rmtree("./data/knowledge_graph/test_alpha_kuzu.db", ignore_errors=True)