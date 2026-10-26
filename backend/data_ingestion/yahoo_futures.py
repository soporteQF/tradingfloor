"""Adaptador Yahoo Finance para futuros (gratis, legal, con retraso).

Yahoo expone contratos continuos: NQ=F, ES=F, YM=F, GC=F.
- 1m:  últimos ~7 días por petición, ~30 días en total
- 5m/15m: ~60 días
- 1h:  ~730 días
- 1d:  varios años

Suficiente para research inicial. Para 1m histórico multi-año se usa
Databento (crédito único) cuando el research lo justifique.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

YAHOO_TICKERS: dict[str, str] = {
    "NQ": "NQ=F",  # E-mini Nasdaq 100
    "ES": "ES=F",  # E-mini S&P 500
    "YM": "YM=F",  # E-mini Dow
    "GC": "GC=F",  # Gold
}

# Límites reales de Yahoo por intervalo (días)
MAX_DAYS = {
    "1m": 7,
    "5m": 59,
    "15m": 59,
    "1h": 729,
    "1d": 3650,
}

# Periodos aceptados por yfinance
DEFAULT_PERIOD = {
    "1m": "7d",
    "5m": "60d",
    "15m": "60d",
    "1h": "2y",
    "1d": "5y",
}


def fetch_bars(symbol: str, timeframe: str, period: str | None = None) -> pd.DataFrame:
    """Descarga barras normalizadas (UTC→ET, ordenadas, sin duplicados).

    Devuelve columnas: symbol, timeframe, ts, open, high, low, close, volume, source
    """
    if symbol not in YAHOO_TICKERS:
        raise ValueError(f"Símbolo no soportado: {symbol}. Usa {list(YAHOO_TICKERS)}")
    if timeframe not in MAX_DAYS:
        raise ValueError(f"Timeframe no soportado: {timeframe}. Usa {list(MAX_DAYS)}")

    ticker = YAHOO_TICKERS[symbol]
    period = period or DEFAULT_PERIOD[timeframe]

    log.info("yfinance: %s (%s) timeframe=%s period=%s", symbol, ticker, timeframe, period)
    raw = yf.download(
        tickers=ticker,
        period=period,
        interval=timeframe,
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if raw is None or raw.empty:
        raise RuntimeError(f"Yahoo devolvió vacío para {symbol} {timeframe} ({period})")

    # yfinance puede devolver MultiIndex en columnas
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw.reset_index()
    # El nombre de la columna de fecha varía según intervalo
    ts_col = next(c for c in ("Datetime", "Date", "index") if c in df.columns)

    out = pd.DataFrame(
        {
            "symbol": symbol,
            "timeframe": timeframe,
            "ts": pd.to_datetime(df[ts_col], utc=True),
            "open": df["Open"].astype(float),
            "high": df["High"].astype(float),
            "low": df["Low"].astype(float),
            "close": df["Close"].astype(float),
            "volume": df.get("Volume", pd.Series(0.0, index=df.index)).astype(float),
            "source": "yahoo",
        }
    )

    # Normalización
    out = out.dropna(subset=["open", "high", "low", "close"])
    out = out.drop_duplicates(subset=["symbol", "timeframe", "ts"])
    out = out.sort_values("ts").reset_index(drop=True)
    out["ts"] = out["ts"].dt.tz_convert("America/New_York")

    return out


def detect_gaps(df: pd.DataFrame) -> dict:
    """Data quality: intervalos anómalos entre barras.

    No usa calendario de bolsa (evita falsos positivos por weekend/holidays).
    Marca gaps mayores a 3x la mediana del intervalo.
    """
    if len(df) < 10:
        return {"ok": False, "reason": "too_few_bars", "bars": len(df), "gaps": 0, "gap_pct": 1.0}

    deltas = df["ts"].diff().dropna().dt.total_seconds()
    median = float(deltas.median())
    if median <= 0:
        return {"ok": False, "reason": "bad_median_interval", "bars": len(df), "gaps": 0, "gap_pct": 1.0}

    gaps = int((deltas > median * 3).sum())
    gap_pct = gaps / len(deltas)

    return {
        "ok": gap_pct <= 0.05,
        "reason": "ok" if gap_pct <= 0.05 else "excessive_gaps",
        "bars": len(df),
        "median_interval_s": median,
        "gaps": gaps,
        "gap_pct": round(gap_pct, 4),
        "first": df["ts"].iloc[0].isoformat(),
        "last": df["ts"].iloc[-1].isoformat(),
    }


def freshness(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"fresh": False, "lag_hours": None}
    last = df["ts"].iloc[-1].to_pydatetime()
    now = datetime.now(timezone.utc)
    lag_h = (now - last.astimezone(timezone.utc)).total_seconds() / 3600
    return {"fresh": lag_h < 72, "lag_hours": round(lag_h, 2), "last_bar": last.isoformat()}
