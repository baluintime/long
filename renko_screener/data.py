"""Daily OHLCV data acquisition.

Two sources:
- ``yahoo``: downloads NSE daily candles via yfinance (symbols suffixed .NS).
- ``csv``: reads per-symbol files ``<SYMBOL>.csv`` from a directory, with
  Date,Open,High,Low,Close,Volume columns — useful offline and in tests.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
DEFAULT_LOOKBACK = "3y"  # enough daily candles to form 78+ Renko bricks


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.rename(columns={c: c.capitalize() for c in frame.columns})
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"missing OHLCV columns: {missing}")
    frame = frame[REQUIRED_COLUMNS].copy()
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    return frame.sort_index()


def fetch_yahoo(symbol: str, period: str = DEFAULT_LOOKBACK) -> pd.DataFrame | None:
    """Fetch daily OHLCV for an NSE symbol from Yahoo Finance."""
    import yfinance as yf  # imported lazily so offline/csv mode needs no network stack

    ticker = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
    try:
        frame = yf.download(
            ticker,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception as exc:  # network / API errors: skip symbol, keep scanning
        log.warning("download failed for %s: %s", ticker, exc)
        return None
    if frame is None or frame.empty:
        log.warning("no data returned for %s", ticker)
        return None
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    return _normalize(frame)


def load_csv(symbol: str, csv_dir: str | Path) -> pd.DataFrame | None:
    """Load daily OHLCV for a symbol from ``<csv_dir>/<SYMBOL>.csv``."""
    path = Path(csv_dir) / f"{symbol}.csv"
    if not path.exists():
        log.warning("csv file not found: %s", path)
        return None
    frame = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
    return _normalize(frame)
