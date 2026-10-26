"""EL ÁRBITRO.

Sin esto, 8 agentes debatiendo son 8 opiniones sin evidencia.
El referee recibe una hipótesis, la mata o la deja pasar, y explica por qué.

Protocolo:
  1. Walk-forward con selección de params en train (purged por construcción:
     test nunca ve datos de train).
  2. Métricas sobre trades OOS agregados (los que el motor no vio al elegir).
  3. Monte Carlo block-bootstrap → distribución de drawdown / ruina.
  4. Param stability → drift entre folds.
  5. Fingerprint estructural → detectar duplicados de overfit conocidos.
  6. Checks → PASS/FAIL con razones legibles.
"""

from __future__ import annotations

import hashlib
import logging

import numpy as np
import pandas as pd

from backtest.engine import BacktestEngine, Trade
from contracts import (
    EntryRule,
    Hypothesis,
    ValidationCheck,
    ValidationResult,
)

from .metrics import compute_metrics, daily_returns, equity_curve, sharpe

log = logging.getLogger(__name__)

# ── Gates (alineados con .env / AGENTS.md) ──
MIN_TRADES = 40
MIN_SHARPE = 1.0
MIN_NET_SHARPE = 0.7
MAX_DD = 0.20
MIN_FOLDS_POSITIVE = 0.6
MAX_PARAM_DRIFT = 0.25
MC_SIMS = 300
MC_BLOCK = 5
MC_MAX_P95_DD = 0.30


# ─────────────────────────────────────────────────────────────
# Grid de parámetros por tipo de entrada (espacio de búsqueda pequeño)
# ─────────────────────────────────────────────────────────────

def param_grid(entry: EntryRule) -> list[dict]:
    if entry.kind == "ema_cross":
        return [{"fast": f, "slow": s} for f, s in [(9, 21), (12, 26), (20, 50), (21, 55)]]
    if entry.kind == "donchian_breakout":
        return [{"lookback": n} for n in (10, 20, 40)]
    if entry.kind == "rsi_extreme":
        return [
            {"period": p, "oversold": 30, "overbought": 70} for p in (7, 14)
        ] + [{"period": 14, "oversold": 25, "overbought": 75}]
    if entry.kind == "zscore_mean_revert":
        return [{"period": p, "threshold": t} for p in (20, 50) for t in (1.5, 2.0)]
    if entry.kind == "vwap_reclaim":
        return [{"period": n} for n in (10, 20, 40)]
    return [{}]


def fingerprint_of(hyp: Hypothesis) -> str:
    return hashlib.sha256(hyp.fingerprint_key().encode()).hexdigest()[:16]


# ─────────────────────────────────────────────────────────────
# Walk-forward
# ─────────────────────────────────────────────────────────────

def walk_forward(
    df: pd.DataFrame,
    hyp: Hypothesis,
    n_folds: int = 8,
    train_frac: float = 0.5,
) -> tuple[list[Trade], list[dict], list[float]]:
    """Devuelve (trades OOS agregados, params elegidos por fold, sharpe por fold)."""
    n = len(df)
    if n < 400:
        return [], [], []

    engine = BacktestEngine()
    fold_size = n // n_folds
    oos_trades: list[Trade] = []
    chosen: list[dict] = []
    fold_sharpes: list[float] = []

    grid = param_grid(hyp.entry)

    for k in range(1, n_folds):
        test_start = k * fold_size
        test_end = min(n, (k + 1) * fold_size)
        train_start = max(0, test_start - int(fold_size * train_frac / (1 - train_frac)))

        train = df.iloc[train_start:test_start]
        test = df.iloc[test_start:test_end]
        if len(train) < 200 or len(test) < 50:
            continue

        # selección de params SOLO en train
        best_params, best_sharpe = None, -np.inf
        for params in grid:
            probe = hyp.model_copy(deep=True)
            probe.entry.params = {**hyp.entry.params, **params}
            res = engine.run(train, probe)
            if len(res.trades) < 8:
                continue
            s = sharpe(daily_returns(res.trades, 50_000.0))
            if s > best_sharpe:
                best_sharpe, best_params = s, params

        if best_params is None:
            continue

        # evaluación en test con params elegidos
        eval_hyp = hyp.model_copy(deep=True)
        eval_hyp.entry.params = {**hyp.entry.params, **best_params}
        test_res = engine.run(test, eval_hyp)

        chosen.append(best_params)
        fold_sharpes.append(sharpe(daily_returns(test_res.trades, 50_000.0)))
        oos_trades.extend(test_res.trades)

    return oos_trades, chosen, fold_sharpes


def _equity_from_trades(trades: list[Trade], start: float) -> pd.Series:
    return equity_curve(trades, start)


# ─────────────────────────────────────────────────────────────
# Monte Carlo
# ─────────────────────────────────────────────────────────────

def monte_carlo(trades: list[Trade], sims: int = MC_SIMS, block: int = MC_BLOCK) -> dict:
    if len(trades) < 20:
        return {"ok": False, "reason": "too_few_trades", "p95_dd": 1.0, "ruin_prob": 1.0}

    pnls = np.array([t.pnl_usd for t in trades], dtype=float)
    n = len(pnls)
    n_blocks = max(1, n // block)

    final_returns, max_dds = [], []
    rng = np.random.default_rng(42)
    for _ in range(sims):
        starts = rng.integers(0, n - block + 1, size=n_blocks)
        sample = np.concatenate([pnls[s:s + block] for s in starts])[:n]
        eq = 50_000.0 + np.cumsum(sample)
        peak = np.maximum.accumulate(eq)
        max_dds.append(float(((eq / peak) - 1).min()))
        final_returns.append(float(eq[-1] - 50_000.0))

    max_dds_arr = np.array(max_dds)
    return {
        "ok": True,
        "p95_dd": float(np.percentile(max_dds_arr, 5)),  # 5º percentil = peor 5%
        "median_dd": float(np.median(max_dds_arr)),
        "ruin_prob": float((np.array(final_returns) < -0.25 * 50_000).mean()),
        "median_final": float(np.median(final_returns)),
    }


# ─────────────────────────────────────────────────────────────
# Param stability
# ─────────────────────────────────────────────────────────────

def param_drift(chosen: list[dict]) -> tuple[float, dict]:
    if len(chosen) < 2:
        return 1.0, {}
    bounds: dict[str, tuple[float, float]] = {}
    drifts: list[float] = []
    keys = set().union(*[set(c) for c in chosen])
    for k in keys:
        vals = [c[k] for c in chosen if k in c]
        if len(vals) < 2:
            continue
        lo, hi = float(min(vals)), float(max(vals))
        bounds[k] = (lo, hi)
        mean = float(np.mean(np.abs(vals)))
        if mean > 0:
            drifts.append((hi - lo) / mean)
    return (float(np.mean(drifts)) if drifts else 0.0), bounds


# ─────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────

class Referee:
    def __init__(self, n_folds: int = 8):
        self.n_folds = n_folds

    def judge(self, hyp: Hypothesis, df: pd.DataFrame) -> ValidationResult:
        if len(df) < 400:
            return self._reject(hyp, "datos insuficientes (<400 barras)")

        trades, chosen, fold_sharpes = walk_forward(df, hyp, n_folds=self.n_folds)
        if not trades:
            return self._reject(hyp, "walk-forward sin trades OOS")

        metrics = compute_metrics(trades, 50_000.0)
        mc = monte_carlo(trades)
        drift, bounds = param_drift(chosen)

        checks = [
            ValidationCheck(name="min_trades", value=metrics.trades, threshold=MIN_TRADES,
                            passed=metrics.trades >= MIN_TRADES),
            ValidationCheck(name="sharpe", value=metrics.sharpe, threshold=MIN_SHARPE,
                            passed=metrics.sharpe >= MIN_SHARPE),
            ValidationCheck(name="net_sharpe", value=metrics.net_sharpe, threshold=MIN_NET_SHARPE,
                            passed=metrics.net_sharpe >= MIN_NET_SHARPE),
            ValidationCheck(name="max_drawdown", value=metrics.max_drawdown, threshold=-MAX_DD,
                            passed=metrics.max_drawdown >= -MAX_DD),
            ValidationCheck(name="profit_factor", value=metrics.profit_factor, threshold=1.2,
                            passed=metrics.profit_factor >= 1.2),
            ValidationCheck(name="fold_consistency",
                            value=round(_positive_ratio(fold_sharpes), 3), threshold=MIN_FOLDS_POSITIVE,
                            passed=_positive_ratio(fold_sharpes) >= MIN_FOLDS_POSITIVE),
            ValidationCheck(name="param_drift", value=round(drift, 3), threshold=MAX_PARAM_DRIFT,
                            passed=drift <= MAX_PARAM_DRIFT),
            ValidationCheck(name="monte_carlo_p95_dd", value=round(mc.get("p95_dd", 1.0), 3),
                            threshold=-MC_MAX_P95_DD, passed=mc.get("p95_dd", 1.0) >= -MC_MAX_P95_DD),
            ValidationCheck(name="ruin_prob", value=round(mc.get("ruin_prob", 1.0), 4), threshold=0.05,
                            passed=mc.get("ruin_prob", 1.0) <= 0.05),
        ]

        failures = [c.name for c in checks if not c.passed]
        passed = not failures

        return ValidationResult(
            hypothesis_id=hyp.id,
            symbol=hyp.symbol,
            passed=passed,
            metrics=metrics,
            checks=checks,
            param_bounds={k: v for k, v in bounds.items()},
            fingerprint=fingerprint_of(hyp),
            failure_reasons=failures,
        )

    @staticmethod
    def _reject(hyp: Hypothesis, reason: str) -> ValidationResult:
        from contracts import ValidationMetrics

        return ValidationResult(
            hypothesis_id=hyp.id, symbol=hyp.symbol, passed=False,
            metrics=ValidationMetrics(),
            checks=[ValidationCheck(name="precondition", value=reason, threshold="ok", passed=False)],
            failure_reasons=["precondition"],
        )


def _positive_ratio(fold_sharpes: list[float]) -> float:
    if not fold_sharpes:
        return 0.0
    return sum(1 for s in fold_sharpes if s > 0) / len(fold_sharpes)
