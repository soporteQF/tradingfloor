"""DuckDB store: barras + ingesta idempotente + calidad de datos."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
    symbol     VARCHAR NOT NULL,
    timeframe  VARCHAR NOT NULL,
    ts         TIMESTAMP WITH TIME ZONE NOT NULL,
    open       DOUBLE NOT NULL,
    high       DOUBLE NOT NULL,
    low        DOUBLE NOT NULL,
    close      DOUBLE NOT NULL,
    volume     DOUBLE DEFAULT 0,
    source     VARCHAR DEFAULT 'unknown',
    ingested_at TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (symbol, timeframe, ts)
);

CREATE TABLE IF NOT EXISTS ingest_log (
    ts          TIMESTAMP DEFAULT current_timestamp,
    symbol      VARCHAR,
    timeframe   VARCHAR,
    source      VARCHAR,
    rows        INTEGER,
    gap_pct     DOUBLE,
    ok          BOOLEAN,
    detail      VARCHAR
);
"""


class DuckStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(self.db_path)
        self.con.execute("PRAGMA threads=4")
        self.con.execute("PRAGMA memory_limit='3GB'")
        self.con.execute(SCHEMA)

    # ── escritura ──────────────────────────────────────────
    def upsert_bars(self, df: pd.DataFrame) -> int:
        """Idempotente: (symbol, timeframe, ts) único."""
        if df.empty:
            return 0
        cols = ["symbol", "timeframe", "ts", "open", "high", "low", "close", "volume", "source"]
        payload = df[cols].copy()
        self.con.register("_incoming", payload)
        before = self.con.execute("SELECT count(*) FROM bars").fetchone()[0]
        self.con.execute(
            """
            INSERT INTO bars (symbol, timeframe, ts, open, high, low, close, volume, source)
            SELECT symbol, timeframe, ts, open, high, low, close, volume, source FROM _incoming
            ON CONFLICT (symbol, timeframe, ts) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                source = excluded.source
            """
        )
        self.con.unregister("_incoming")
        after = self.con.execute("SELECT count(*) FROM bars").fetchone()[0]
        return after - before

    def log_ingest(self, symbol: str, timeframe: str, source: str, rows: int,
                   gap_pct: float, ok: bool, detail: str = "") -> None:
        self.con.execute(
            "INSERT INTO ingest_log (symbol, timeframe, source, rows, gap_pct, ok, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [symbol, timeframe, source, rows, gap_pct, ok, detail],
        )

    # ── lectura ────────────────────────────────────────────
    def read_bars(self, symbol: str, timeframe: str,
                  start: str | None = None, end: str | None = None) -> pd.DataFrame:
        q = "SELECT ts, open, high, low, close, volume FROM bars WHERE symbol=? AND timeframe=?"
        params: list = [symbol, timeframe]
        if start:
            q += " AND ts >= ?"
            params.append(start)
        if end:
            q += " AND ts <= ?"
            params.append(end)
        q += " ORDER BY ts"
        df = self.con.execute(q, params).df()
        if not df.empty:
            df = df.set_index("ts")
        return df

    def coverage(self) -> pd.DataFrame:
        return self.con.execute(
            """
            SELECT symbol, timeframe, count(*) AS bars,
                   min(ts) AS first_bar, max(ts) AS last_bar
            FROM bars GROUP BY symbol, timeframe ORDER BY symbol, timeframe
            """
        ).df()

    def last_ingest(self) -> pd.DataFrame:
        return self.con.execute(
            "SELECT * FROM ingest_log ORDER BY ts DESC LIMIT 50"
        ).df()

    def close(self) -> None:
        self.con.close()
