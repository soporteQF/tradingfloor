"""Motor de backtest event-driven, honesto con costes.

Diseño deliberado:
- Una posición a la vez (sin pyramiding, sin hedge) → fácil de auditar.
- Costes reales: comisión round-turn + slippage por lado (ticks).
- Sin look-ahead: señales calculadas con barras cerradas, entrada al open
  de la barra siguiente.
- Path-dependent exits (stop, target, trailing, time) → no vectorizado puro,
  pero loop numpy tight. Suficiente para research nocturno.

Limitación conocida: el drawdown se mide sobre equity realizada (trade-level).
Es ligeramente optimista vs mark-to-market, y está documentado en el reporte.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from contracts import EntryRule, ExitRule, Hypothesis, SizingRule, Symbol


# ─────────────────────────────────────────────────────────────
# Especificaciones de contrato
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SymbolSpec:
    point_value: float   # USD por 1 punto
    tick_size: float     # tamaño de tick en puntos
    commission_rt: float # USD round-turn por contrato


SPECS: dict[str, SymbolSpec] = {
    # Contratos full-size
    "NQ": SymbolSpec(point_value=20.0, tick_size=0.25, commission_rt=5.0),
    "ES": SymbolSpec(point_value=50.0, tick_size=0.25, commission_rt=5.0),
    "YM": SymbolSpec(point_value=5.0, tick_size=1.0, commission_rt=5.0),
    "GC": SymbolSpec(point_value=100.0, tick_size=0.10, commission_rt=5.0),
    # Micros — el instrumento realista para cuentas de fondeo pequeñas
    "MNQ": SymbolSpec(point_value=2.0, tick_size=0.25, commission_rt=2.0),
    "MES": SymbolSpec(point_value=5.0, tick_size=0.25, commission_rt=2.0),
    "MYM": SymbolSpec(point_value=0.5, tick_size=1.0, commission_rt=2.0),
    "MGC": SymbolSpec(point_value=10.0, tick_size=0.10, commission_rt=2.0),
}


@dataclass
class Trade:
    entry_ts: datetime
    exit_ts: datetime
    direction: int
    entry_price: float
    exit_price: float
    contracts: int
    pnl_usd: float
    costs_usd: float
    bars_held: int
    exit_reason: str


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    bars: int = 0
    exposure_pct: float = 0.0


# ─────────────────────────────────────────────────────────────
# Indicadores
# ─────────────────────────────────────────────────────────────

def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def zscore(s: pd.Series, n: int = 20) -> pd.Series:
    m = s.rolling(n).mean()
    sd = s.rolling(n).std()
    return (s - m) / sd.replace(0, np.nan)


def rolling_vwap(df: pd.DataFrame, n: int = 20) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    pv = (tp * df["volume"]).rolling(n).sum()
    v = df["volume"].rolling(n).sum()
    return (pv / v.replace(0, np.nan)).fillna(tp.rolling(n).mean())


# ─────────────────────────────────────────────────────────────
# Señales
# ─────────────────────────────────────────────────────────────

def build_signals(df: pd.DataFrame, entry: EntryRule, direction: str) -> pd.Series:
    """Devuelve señal por barra: +1 long, -1 short, 0 nada."""
    p = entry.params
    signal = pd.Series(0, index=df.index, dtype=int)

    if entry.kind == "ema_cross":
        f = ema(df["close"], int(p.get("fast", 20)))
        s = ema(df["close"], int(p.get("slow", 50)))
        cross_up = (f > s) & (f.shift() <= s.shift())
        cross_dn = (f < s) & (f.shift() >= s.shift())
        signal[cross_up] = 1
        signal[cross_dn] = -1

    elif entry.kind == "donchian_breakout":
        n = int(p.get("lookback", 20))
        hh = df["high"].rolling(n).max().shift()
        ll = df["low"].rolling(n).min().shift()
        signal[df["close"] > hh] = 1
        signal[df["close"] < ll] = -1

    elif entry.kind == "rsi_extreme":
        r = rsi(df["close"], int(p.get("period", 14)))
        signal[r < p.get("oversold", 30)] = 1
        signal[r > p.get("overbought", 70)] = -1

    elif entry.kind == "zscore_mean_revert":
        z = zscore(df["close"], int(p.get("period", 20)))
        t = p.get("threshold", 2.0)
        signal[z < -t] = 1
        signal[z > t] = -1

    elif entry.kind == "vwap_reclaim":
        v = rolling_vwap(df, int(p.get("period", 20)))
        signal[(df["close"] > v) & (df["close"].shift() <= v.shift())] = 1
        signal[(df["close"] < v) & (df["close"].shift() >= v.shift())] = -1

    else:
        raise ValueError(f"entry.kind no soportado: {entry.kind}")

    if direction == "long":
        signal[signal < 0] = 0
    elif direction == "short":
        signal[signal > 0] = 0

    return signal


def contracts_for(sizing: SizingRule, equity: float, atr_value: float, spec: SymbolSpec) -> int:
    if sizing.kind == "fixed_contracts":
        return max(1, int(sizing.params.get("contracts", 1)))
    if sizing.kind == "atr_risk":
        risk_usd = sizing.params.get("risk_usd", 250.0)
        risk_per_contract = max(atr_value * spec.point_value, 1e-9)
        return max(1, min(50, int(risk_usd / risk_per_contract)))
    # vol_target (aproximación conservadora → 1 contrato)
    return max(1, int(sizing.params.get("contracts", 1)))


# ─────────────────────────────────────────────────────────────
# Motor
# ─────────────────────────────────────────────────────────────

class BacktestEngine:
    def __init__(self, slippage_ticks: float = 1.0, starting_equity: float = 50_000.0):
        self.slippage_ticks = slippage_ticks
        self.starting_equity = starting_equity

    def run(self, df: pd.DataFrame, hyp: Hypothesis) -> BacktestResult:
        if len(df) < 100:
            return BacktestResult(bars=len(df))

        spec = SPECS[hyp.contract or hyp.symbol]
        o = df["open"].to_numpy(float)
        h = df["high"].to_numpy(float)
        l = df["low"].to_numpy(float)
        c = df["close"].to_numpy(float)
        atr_arr = atr(df, int(hyp.exit.params.get("atr_period", 14))).to_numpy(float)
        signals = build_signals(df, hyp.entry, hyp.direction).to_numpy(int)
        ts = df.index

        slip = self.slippage_ticks * spec.tick_size
        costs_per_contract = spec.commission_rt + 2 * slip * spec.point_value

        trades: list[Trade] = []
        equity = self.starting_equity
        equity_pts: list[tuple] = []

        pos = 0           # 0 flat, +1 long, -1 short
        entry_px = entry_atr = 0.0
        entry_idx = 0
        stop = target = 0.0
        trail_extreme = 0.0
        contracts = 0

        exit_kind = hyp.exit.kind
        ep = hyp.exit.params
        stop_mult = ep.get("stop_atr", 2.0)
        r_mult = ep.get("r_multiple", 2.0)
        trail_mult = ep.get("atr_mult", 2.0)
        time_bars = int(ep.get("bars", 20))

        for i in range(60, len(df) - 1):
            # ── gestión de posición abierta ──
            if pos != 0:
                bars_held = i - entry_idx
                exit_px = None
                reason = ""

                if pos == 1:
                    if exit_kind == "atr_trailing":
                        trail_extreme = max(trail_extreme, h[i])
                        stop = max(stop, trail_extreme - trail_mult * entry_atr)
                        if l[i] <= stop:
                            exit_px, reason = stop - slip, "stop"
                    elif exit_kind == "fixed_r":
                        if l[i] <= stop:
                            exit_px, reason = stop - slip, "stop"
                        elif h[i] >= target:
                            exit_px, reason = target - slip, "target"
                    elif exit_kind == "time_stop":
                        if bars_held >= time_bars:
                            exit_px, reason = c[i] - slip, "time"
                    elif exit_kind == "opposite_signal":
                        if signals[i] == -1:
                            exit_px, reason = c[i] - slip, "opposite"
                else:  # short
                    if exit_kind == "atr_trailing":
                        trail_extreme = min(trail_extreme, l[i])
                        stop = min(stop, trail_extreme + trail_mult * entry_atr)
                        if h[i] >= stop:
                            exit_px, reason = stop + slip, "stop"
                    elif exit_kind == "fixed_r":
                        if h[i] >= stop:
                            exit_px, reason = stop + slip, "stop"
                        elif l[i] <= target:
                            exit_px, reason = target + slip, "target"
                    elif exit_kind == "time_stop":
                        if bars_held >= time_bars:
                            exit_px, reason = c[i] + slip, "time"
                    elif exit_kind == "opposite_signal":
                        if signals[i] == 1:
                            exit_px, reason = c[i] + slip, "opposite"

                if exit_px is not None:
                    gross = (exit_px - entry_px) * pos * spec.point_value * contracts
                    costs = costs_per_contract * contracts
                    pnl = gross - costs
                    equity += pnl
                    trades.append(Trade(
                        entry_ts=ts[entry_idx].to_pydatetime(),
                        exit_ts=ts[i].to_pydatetime(),
                        direction=pos, entry_price=entry_px, exit_price=exit_px,
                        contracts=contracts, pnl_usd=pnl, costs_usd=costs,
                        bars_held=bars_held, exit_reason=reason,
                    ))
                    equity_pts.append((ts[i], equity))
                    pos = 0

            # ── apertura de nueva posición ──
            if pos == 0 and signals[i] != 0:
                contracts = contracts_for(hyp.sizing, equity, float(atr_arr[i]), spec)
                # Slippage SIEMPRE en contra: long paga más, short recibe menos.
                entry_px = o[i + 1] + (slip if signals[i] == 1 else -slip)
                entry_atr = max(float(atr_arr[i]), spec.tick_size * 2)
                entry_idx = i + 1
                pos = signals[i]
                trail_extreme = entry_px
                if exit_kind in ("fixed_r", "atr_trailing"):
                    if pos == 1:
                        stop = entry_px - stop_mult * entry_atr
                        target = entry_px + r_mult * (entry_px - stop)
                    else:
                        stop = entry_px + stop_mult * entry_atr
                        target = entry_px - r_mult * (stop - entry_px)

        equity_series = pd.Series(
            [self.starting_equity] + [v for _, v in equity_pts],
            index=[ts[60]] + [t for t, _ in equity_pts] if equity_pts else [ts[60]],
        ).sort_index()

        exposure = (
            sum(t.bars_held for t in trades) / len(df) if trades else 0.0
        )

        return BacktestResult(trades=trades, equity=equity_series, bars=len(df), exposure_pct=exposure)
