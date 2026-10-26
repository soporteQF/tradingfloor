"""Métricas de una curva de equity + lista de trades.

Decisión de diseño importante:
  El Sharpe se calcula sobre RETORNOS POR TRADE normalizados por el equity
  inicial, agregados por día. NO sobre `equity.pct_change()`.

  Motivo: si una estrategia pierde más del 100% del capital, la equity cruza
  cero y el pct_change produce valores absurdos (signos invertidos, infinitos).
  Un Sharpe calculado así es basura. El retorno por trade es robusto a eso.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtest.engine import Trade
from contracts import ValidationMetrics


def trade_returns(trades: list[Trade], starting_equity: float) -> pd.Series:
    """Retorno de cada trade respecto al capital inicial, indexado por fecha de cierre."""
    if not trades:
        return pd.Series(dtype=float)
    ts = pd.to_datetime([t.exit_ts for t in trades])
    rets = np.array([t.pnl_usd for t in trades], dtype=float) / starting_equity
    return pd.Series(rets, index=ts).sort_index()


def daily_returns(trades: list[Trade], starting_equity: float) -> pd.Series:
    """Suma retornos por día (una estrategia puede hacer varios trades/día)."""
    r = trade_returns(trades, starting_equity)
    if r.empty:
        return r
    return r.resample("1D").sum()


def sharpe(returns: pd.Series, periods: int = 252) -> float:
    if len(returns) < 3:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0:
        return 0.0
    return float(returns.mean() / std * np.sqrt(periods))


def sortino(returns: pd.Series, periods: int = 252) -> float:
    if len(returns) < 3:
        return 0.0
    downside = returns[returns < 0]
    if len(downside) < 2:
        return 0.0
    dd = float(downside.std(ddof=1))
    if dd <= 0:
        return 0.0
    return float(returns.mean() / dd * np.sqrt(periods))


def equity_curve(trades: list[Trade], starting_equity: float) -> pd.Series:
    """Equity realizada. Se recorta a 0 si el capital se pierde (ruina)."""
    if not trades:
        return pd.Series([starting_equity])
    ts = pd.to_datetime([t.exit_ts for t in trades])
    eq = np.cumsum([t.pnl_usd for t in trades]) + starting_equity
    eq = np.clip(eq, 0.0, None)
    return pd.Series(np.concatenate([[starting_equity], eq]),
                     index=pd.DatetimeIndex([ts[0] - pd.Timedelta(days=1), *ts]))


def max_drawdown(equity: pd.Series) -> float:
    if equity is None or len(equity) < 2:
        return 0.0
    eq = equity.sort_index().astype(float)
    peak = eq.cummax().replace(0, np.nan)
    dd = (eq / peak) - 1.0
    return float(dd.min())


def compute_metrics(trades: list[Trade], starting_equity: float = 50_000.0) -> ValidationMetrics:
    if not trades:
        return ValidationMetrics()

    pnls = np.array([t.pnl_usd for t in trades], dtype=float)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    gross_win = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    profit_factor = gross_win / gross_loss if gross_loss > 0 else (99.9 if gross_win > 0 else 0.0)

    rets = daily_returns(trades, starting_equity)
    eq = equity_curve(trades, starting_equity)
    final_equity = float(eq.iloc[-1])
    total_costs = float(sum(t.costs_usd for t in trades))

    return ValidationMetrics(
        trades=len(trades),
        win_rate=round(float(len(wins) / len(trades)), 4),
        profit_factor=round(profit_factor, 3),
        expectancy=round(float(pnls.mean()), 2),
        sharpe=round(sharpe(rets), 3),
        sortino=round(sortino(rets), 3),
        max_drawdown=round(max_drawdown(eq), 4),
        total_return=round((final_equity - starting_equity) / starting_equity, 4),
        avg_trade=round(float(pnls.mean()), 2),
        exposure=round(sum(t.bars_held for t in trades) / max(1, len(trades)), 2),
        net_sharpe=round(sharpe(rets), 3),
    )
