"""VALIDATION — el árbitro con memoria.

Recibe hipótesis, carga sus datos, las juzga con Referee y registra:
  - rechazo  → ErrorNode (kind inferido de los checks fallidos) + HypothesisRecord
  - aprobado → StrategyDNA + InsightNode + HypothesisRecord

Nada se descarta en silencio: cada muerte tiene causa escrita en el grafo.
"""

from __future__ import annotations

import logging

import pandas as pd

from contracts import (
    ErrorKind,
    ErrorNode,
    Hypothesis,
    InsightNode,
    StrategyDNA,
    StrategyStatus,
    ValidationResult,
)
from validation.referee import Referee, fingerprint_of

from .base import Agent

log = logging.getLogger(__name__)

_CHECK_TO_ERROR = {
    "param_drift": ErrorKind.PARAM_UNSTABLE,
    "fold_consistency": ErrorKind.NO_EDGE,
    "sharpe": ErrorKind.NO_EDGE,
    "net_sharpe": ErrorKind.NO_EDGE,
    "profit_factor": ErrorKind.NO_EDGE,
    "min_trades": ErrorKind.NO_EDGE,
    "max_drawdown": ErrorKind.RISK_BREACH,
    "monte_carlo_p95_dd": ErrorKind.RISK_BREACH,
    "ruin_prob": ErrorKind.RISK_BREACH,
    "precondition": ErrorKind.DATA_QUALITY,
}


def infer_error_kind(failure_names: list[str]) -> ErrorKind:
    for name in failure_names:
        if name in _CHECK_TO_ERROR:
            return _CHECK_TO_ERROR[name]
    return ErrorKind.UNKNOWN


class ValidationAgent(Agent):
    name = "validation"
    role = "Mata o deja pasar hipótesis. Nunca falla en silencio."

    def __init__(self, kg, referee: Referee | None = None):
        super().__init__(kg=kg)
        self.referee = referee or Referee()

    def validate_many(self, hypotheses: list[Hypothesis],
                      data: dict[tuple[str, str], pd.DataFrame]) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for hyp in hypotheses:
            df = data.get((hyp.symbol, hyp.timeframe))
            if df is None or len(df) < 400:
                result = self.referee._reject(hyp, "sin datos suficientes para el par símbolo/timeframe")
            else:
                result = self.referee.judge(hyp, df)

            self._log_verdict(hyp, result)
            results.append(result)

            self.log(
                "%s %s %s/%s → %s (sharpe=%.2f dd=%.1f%% trades=%d)",
                hyp.symbol, hyp.timeframe, hyp.entry.kind, hyp.exit.kind,
                "PASS" if result.passed else "FAIL",
                result.metrics.sharpe, result.metrics.max_drawdown * 100,
                result.metrics.trades,
            )

        passed = sum(1 for r in results if r.passed)
        self.log("veredictos: %d evaluadas · %d pasan · %d mueren", len(results), passed, len(results) - passed)
        self._remember({"evaluated": len(results), "passed": passed})
        return results

    # ── memoria ───────────────────────────────────────────
    def _log_verdict(self, hyp: Hypothesis, result: ValidationResult) -> None:
        if self.kg is None:
            return

        self.kg.record_hypothesis(hyp, result)

        if result.passed:
            dna = StrategyDNA(
                hypothesis_id=hyp.id,
                symbol=hyp.symbol,
                timeframe=hyp.timeframe,
                entry=hyp.entry,
                exit=hyp.exit,
                sizing=hyp.sizing,
                regime_gates=hyp.regime_gate,
                performance=result.metrics,
                fingerprint=result.fingerprint,
                status=StrategyStatus.VALIDATED,
            )
            self.kg.write_strategy(dna)
            self.kg.link_strategy_hypothesis(dna.id, hyp.id)

            insight = InsightNode(
                kind="validated_setup",
                description=(
                    f"{hyp.symbol} {hyp.timeframe}: {hyp.entry.kind} + {hyp.exit.kind} "
                    f"sobrevive el árbitro (sharpe {result.metrics.sharpe}, "
                    f"dd {result.metrics.max_drawdown:.1%}, {result.metrics.trades} trades)."
                ),
                symbol=hyp.symbol,
                confidence=min(0.95, 0.5 + result.metrics.sharpe / 10),
                source_agent=self.name,
            )
            self.kg.write_insight(insight)
        else:
            kind = infer_error_kind(result.failure_reasons)
            root_cause = _explain(result)
            err = ErrorNode(
                kind=kind,
                strategy_id=hyp.id,
                symbol=hyp.symbol,
                regime=hyp.regime_gate[0] if hyp.regime_gate else None,
                root_cause=root_cause,
                evidence={
                    "entry": hyp.entry.kind,
                    "exit": hyp.exit.kind,
                    "params": hyp.entry.params,
                    "checks": {c.name: c.value for c in result.checks if not c.passed},
                },
            )
            self.kg.write_error(err)


def _explain(result: ValidationResult) -> str:
    """Convierte checks fallidos en una frase legible (causa raíz)."""
    failed = [c for c in result.checks if not c.passed]
    if not failed:
        return "rechazada sin detalle"
    parts = []
    for c in failed:
        parts.append(f"{c.name}={c.value} (umbral {c.threshold})")
    return "Falló: " + "; ".join(parts)
