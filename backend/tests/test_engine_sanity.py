"""Sanity tests del motor de backtest.

La prueba decisiva: sobre un RANDOM WALK no hay edge posible. Cualquier
estrategia debe rendir ~0 (negativo después de costes). Si una entrada
genera Sharpe alto en datos aleatorios, el motor tiene look-ahead o un bug
de contabilidad.

Estos tests son el guardián del árbitro. Si fallan, NO se confía en ningún
PASS del sistema.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.engine import BacktestEngine
from contracts import EntryRule, ExitRule, Hypothesis, SizingRule
from validation.metrics import compute_metrics, daily_returns, sharpe

TF = "1h"


def random_walk(n: int = 3000, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0, 0.0015, n)
    close = 15000 * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(rng.normal(0, 0.0007, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.0007, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="America/New_York")
    return pd.DataFrame(
        {"open": open_, "high": np.maximum.reduce([open_, close, high]),
         "low": np.minimum.reduce([open_, close, low]), "close": close,
         "volume": rng.integers(100, 1000, n).astype(float)},
        index=idx,
    )


def make_hyp(entry: EntryRule, exit_: ExitRule) -> Hypothesis:
    return Hypothesis(
        symbol="NQ", timeframe=TF, direction="both",
        entry=entry, exit=exit_,
        sizing=SizingRule(kind="fixed_contracts", params={"contracts": 1}),
    )


ENTRIES = [
    EntryRule(kind="ema_cross", params={"fast": 9, "slow": 21}),
    EntryRule(kind="donchian_breakout", params={"lookback": 20}),
    EntryRule(kind="rsi_extreme", params={"period": 14, "oversold": 30, "overbought": 70}),
    EntryRule(kind="zscore_mean_revert", params={"period": 20, "threshold": 2.0}),
    EntryRule(kind="vwap_reclaim", params={"period": 20}),
]

EXITS = [
    ExitRule(kind="fixed_r", params={"stop_atr": 2.0, "r_multiple": 2.0}),
    ExitRule(kind="atr_trailing", params={"stop_atr": 2.0, "atr_mult": 2.5}),
    ExitRule(kind="time_stop", params={"bars": 20}),
    ExitRule(kind="opposite_signal", params={}),
]


@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e.kind)
@pytest.mark.parametrize("exit_", EXITS, ids=lambda e: e.kind)
def test_no_edge_on_random_walk(seed: int, entry: EntryRule, exit_: ExitRule) -> None:
    df = random_walk(seed=seed)
    res = BacktestEngine(slippage_ticks=1.0).run(df, make_hyp(entry, exit_))

    if len(res.trades) < 30:
        pytest.skip("pocos trades para juzgar")

    m = compute_metrics(res.trades, 50_000.0)
    s = sharpe(daily_returns(res.trades, 50_000.0))

    # Test estadístico correcto para muestras pequeñas: ¿la expectancy es
    # significativamente > 0? En un random walk no debe serlo.
    pnls = np.array([t.pnl_usd for t in res.trades], dtype=float)
    t_stat = pnls.mean() / (pnls.std(ddof=1) / np.sqrt(len(pnls)))

    assert t_stat < 3.0, (
        f"t-stat {t_stat:.2f} en random walk para {entry.kind}/{exit_.kind} → "
        f"edge inexistente pero significativo. trades={m.trades} exp={m.expectancy}"
    )
    # Guarda gruesa contra look-ahead grosero
    assert s < 5.0, (
        f"Sharpe POSITIVO {s:.2f} en random walk para {entry.kind}/{exit_.kind} → "
        f"sospecha de look-ahead. trades={m.trades} ret={m.total_return:.3%}"
    )


def test_costs_reduce_pnl() -> None:
    """Mismo trade con y sin costes: el neto debe ser menor (o igual)."""
    df = random_walk(seed=5)
    hyp = make_hyp(ENTRIES[0], EXITS[0])

    free = BacktestEngine(slippage_ticks=0.0).run(df, hyp)
    costly = BacktestEngine(slippage_ticks=2.0).run(df, hyp)

    free_pnl = sum(t.pnl_usd for t in free.trades)
    costly_pnl = sum(t.pnl_usd for t in costly.trades)
    assert costly_pnl < free_pnl, "los costes no están reduciendo el PnL"


def test_equity_never_negative_after_clip() -> None:
    df = random_walk(seed=7)
    hyp = make_hyp(EntryRule(kind="ema_cross", params={"fast": 5, "slow": 10}), EXITS[0])
    res = BacktestEngine().run(df, hyp)
    m = compute_metrics(res.trades, 50_000.0)
    assert m.max_drawdown >= -1.0
