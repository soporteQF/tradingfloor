"""Cliente KuzuDB — la memoria colectiva del floor.

Regla de oro: antes de proponer una hipótesis, Research consulta
`fingerprint_was_rejected()`. Si ya murió, no se repite.

Concurrencia: KuzuDB embebe el motor. Un solo proceso escritor.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import kuzu

from contracts import ErrorNode, Hypothesis, InsightNode, StrategyDNA, ValidationResult

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


DDL = [
    """CREATE NODE TABLE IF NOT EXISTS Error(
        id STRING, kind STRING, strategy_id STRING, symbol STRING, regime STRING,
        root_cause STRING, evidence STRING, created_at STRING, PRIMARY KEY (id))""",
    """CREATE NODE TABLE IF NOT EXISTS Insight(
        id STRING, kind STRING, note STRING, regime STRING, symbol STRING,
        confidence DOUBLE, source_agent STRING, created_at STRING, PRIMARY KEY (id))""",
    """CREATE NODE TABLE IF NOT EXISTS Strategy(
        id STRING, hypothesis_id STRING, symbol STRING, timeframe STRING,
        entry_kind STRING, exit_kind STRING, fingerprint STRING, status STRING,
        sharpe DOUBLE, max_drawdown DOUBLE, trades INT64, created_at STRING,
        PRIMARY KEY (id))""",
    """CREATE NODE TABLE IF NOT EXISTS HypothesisRecord(
        id STRING, fingerprint STRING, symbol STRING, timeframe STRING,
        entry_kind STRING, exit_kind STRING, passed BOOLEAN, sharpe DOUBLE,
        created_at STRING, PRIMARY KEY (id))""",
    """CREATE REL TABLE IF NOT EXISTS CAUSES(FROM Error TO Insight, kind STRING, created_at STRING)""",
    """CREATE REL TABLE IF NOT EXISTS DERIVED_FROM(FROM Strategy TO HypothesisRecord, created_at STRING)""",
    """CREATE REL TABLE IF NOT EXISTS VALIDATED_BY(FROM HypothesisRecord TO Insight, kind STRING, created_at STRING)""",
    # Nota: Kuzu indexa automáticamente la PRIMARY KEY. Índices secundarios
    # no son necesarios a esta escala (<100k nodos) y su sintaxis cambia
    # entre versiones; se omiten a propósito.
]


class KnowledgeGraph:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = kuzu.Database(str(self.path))
        self.conn = kuzu.Connection(self.db)
        self._init_schema()

    def _init_schema(self) -> None:
        for stmt in DDL:
            try:
                self.conn.execute(stmt)
            except RuntimeError as exc:
                msg = str(exc).lower()
                if "already exists" in msg or "duplicated" in msg or "duplicate" in msg:
                    continue
                log.error("DDL falló: %s\n  %s", stmt.strip()[:90], exc)
                raise

    # ── escritura ─────────────────────────────────────────
    def write_error(self, err: ErrorNode) -> None:
        self.conn.execute(
            "CREATE (e:Error {id: $id, kind: $kind, strategy_id: $sid, symbol: $sym, "
            "regime: $reg, root_cause: $cause, evidence: $ev, created_at: $ts})",
            {
                "id": err.id, "kind": err.kind.value, "sid": err.strategy_id or "",
                "sym": err.symbol or "", "reg": err.regime or "",
                "cause": err.root_cause, "ev": json.dumps(err.evidence, default=str),
                "ts": err.created_at.isoformat(),
            },
        )

    def write_insight(self, ins: InsightNode) -> None:
        self.conn.execute(
            "CREATE (i:Insight {id: $id, kind: $kind, note: $txt, regime: $reg, "
            "symbol: $sym, confidence: $conf, source_agent: $src, created_at: $ts})",
            {
                "id": ins.id, "kind": ins.kind, "txt": ins.description,
                "reg": ins.regime or "", "sym": ins.symbol or "",
                "conf": ins.confidence, "src": ins.source_agent,
                "ts": ins.created_at.isoformat(),
            },
        )

    def write_strategy(self, dna: StrategyDNA) -> None:
        self.conn.execute(
            "CREATE (s:Strategy {id: $id, hypothesis_id: $hyp, symbol: $sym, timeframe: $tf, "
            "entry_kind: $ek, exit_kind: $xk, fingerprint: $fp, status: $st, "
            "sharpe: $sh, max_drawdown: $dd, trades: $tr, created_at: $ts})",
            {
                "id": dna.id, "hyp": dna.hypothesis_id, "sym": dna.symbol,
                "tf": dna.timeframe, "ek": dna.entry.kind, "xk": dna.exit.kind,
                "fp": dna.fingerprint, "st": dna.status.value,
                "sh": dna.performance.sharpe, "dd": dna.performance.max_drawdown,
                "tr": dna.performance.trades, "ts": dna.created_at.isoformat(),
            },
        )

    def record_hypothesis(self, hyp: Hypothesis, result: ValidationResult) -> None:
        self.conn.execute(
            "CREATE (h:HypothesisRecord {id: $id, fingerprint: $fp, symbol: $sym, "
            "timeframe: $tf, entry_kind: $ek, exit_kind: $xk, passed: $ok, "
            "sharpe: $sh, created_at: $ts})",
            {
                "id": hyp.id, "fp": result.fingerprint or "",
                "sym": hyp.symbol, "tf": hyp.timeframe,
                "ek": hyp.entry.kind, "xk": hyp.exit.kind,
                "ok": result.passed, "sh": result.metrics.sharpe,
                "ts": result.validated_at.isoformat(),
            },
        )

    def link_error_insight(self, error_id: str, insight_id: str, kind: str = "prevented_by") -> None:
        self.conn.execute(
            "MATCH (e:Error {id: $eid}), (i:Insight {id: $iid}) "
            "CREATE (e)-[:CAUSES {kind: $k, created_at: $ts}]->(i)",
            {"eid": error_id, "iid": insight_id, "k": kind, "ts": _now_iso()},
        )

    def link_strategy_hypothesis(self, strategy_id: str, hypothesis_id: str) -> None:
        self.conn.execute(
            "MATCH (s:Strategy {id: $sid}), (h:HypothesisRecord {id: $hid}) "
            "CREATE (s)-[:DERIVED_FROM {created_at: $ts}]->(h)",
            {"sid": strategy_id, "hid": hypothesis_id, "ts": _now_iso()},
        )

    # ── lectura (la parte que hace que "aprendan") ─────────
    def fingerprint_was_rejected(self, fingerprint: str) -> bool:
        if not fingerprint:
            return False
        res = self.conn.execute(
            "MATCH (h:HypothesisRecord {fingerprint: $fp}) WHERE h.passed = false RETURN count(h)",
            {"fp": fingerprint},
        )
        row = res.get_next()
        return bool(row and row[0] and int(row[0]) > 0)

    def failed_fingerprints(self, limit: int = 500) -> set[str]:
        res = self.conn.execute(
            "MATCH (h:HypothesisRecord) WHERE h.passed = false "
            "RETURN h.fingerprint LIMIT $n", {"n": limit},
        )
        out: set[str] = set()
        while res.has_next():
            row = res.get_next()
            if row and row[0]:
                out.add(row[0])
        return out

    def failure_by_entry_kind(self) -> dict[str, int]:
        res = self.conn.execute(
            "MATCH (h:HypothesisRecord) WHERE h.passed = false "
            "RETURN h.entry_kind, count(h)"
        )
        out: dict[str, int] = {}
        while res.has_next():
            row = res.get_next()
            out[str(row[0])] = int(row[1])
        return out

    def stats(self) -> dict:
        out = {}
        for label, query in {
            "errors": "MATCH (e:Error) RETURN count(e)",
            "insights": "MATCH (i:Insight) RETURN count(i)",
            "strategies": "MATCH (s:Strategy) RETURN count(s)",
            "hypotheses": "MATCH (h:HypothesisRecord) RETURN count(h)",
            "rejected": "MATCH (h:HypothesisRecord) WHERE h.passed = false RETURN count(h)",
            "passed": "MATCH (h:HypothesisRecord) WHERE h.passed = true RETURN count(h)",
        }.items():
            res = self.conn.execute(query)
            out[label] = int(res.get_next()[0])
        return out

    def query(self, cypher: str, params: dict = None) -> list[dict]:
        """Ejecuta query Cypher arbitrario y devuelve lista de dicts."""
        params = params or {}
        res = self.conn.execute(cypher, params)
        out = []
        while res.has_next():
            row = res.get_next()
            if row:
                # Convertir a dict usando nombres de columnas
                # kuzu result tiene get_column_names()
                try:
                    cols = res.get_column_names()
                    out.append(dict(zip(cols, row)))
                except Exception:
                    # Fallback: índice numérico
                    out.append({f"col_{i}": v for i, v in enumerate(row)})
        return out

    def close(self) -> None:
        pass
