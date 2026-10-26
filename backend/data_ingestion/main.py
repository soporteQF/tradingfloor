"""CLI de ingesta: python -m data_ingestion.main --symbols NQ ES --timeframes 1h 1d"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from .store import DuckStore
from .yahoo_futures import detect_gaps, fetch_bars, freshness

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("ingestion")

SYMBOLS = ["NQ", "ES", "YM", "GC"]
TIMEFRAMES = ["1d", "1h", "15m"]


def run(symbols: list[str], timeframes: list[str], db_path: str) -> int:
    store = DuckStore(db_path)
    failures = 0

    for symbol in symbols:
        for tf in timeframes:
            try:
                df = fetch_bars(symbol, tf)
                quality = detect_gaps(df)
                added = store.upsert_bars(df)
                store.log_ingest(
                    symbol=symbol, timeframe=tf, source="yahoo", rows=len(df),
                    gap_pct=quality["gap_pct"], ok=quality["ok"],
                    detail=str(quality),
                )
                fresh = freshness(df)
                log.info(
                    "%s %-3s rows=%-6d new=%-5d gaps=%.1f%% fresh=%s lag=%.1fh",
                    symbol, tf, len(df), added, quality["gap_pct"] * 100,
                    fresh["fresh"], fresh["lag_hours"] or -1,
                )
                if not quality["ok"]:
                    log.warning("%s %s calidad de datos dudosa: %s", symbol, tf, quality["reason"])
            except Exception as exc:  # noqa: BLE001
                failures += 1
                log.error("%s %s FALLÓ: %s", symbol, tf, exc)

    log.info("--- cobertura ---\n%s", store.coverage().to_string(index=False))
    store.close()
    return failures


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="NEXUS — ingesta Yahoo futuros")
    p.add_argument("--symbols", nargs="+", default=SYMBOLS, choices=SYMBOLS)
    p.add_argument("--timeframes", nargs="+", default=TIMEFRAMES)
    p.add_argument("--db", default=os.getenv("DUCKDB_PATH", "./data/processed/analytics.duckdb"))
    args = p.parse_args(argv)

    failures = run(args.symbols, args.timeframes, args.db)
    return 1 if failures == len(args.symbols) * len(args.timeframes) else 0


if __name__ == "__main__":
    sys.exit(main())
