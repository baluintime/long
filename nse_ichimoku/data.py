"""Daily OHLC data for NSE symbols.

Yahoo Finance is the default source (NSE tickers carry a ``.NS`` suffix)
and is downloaded in batches so a couple of thousand symbols stay
practical. A directory of ``<SYMBOL>.csv`` files is supported as an
offline source.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["Open", "High", "Low", "Close"]
DEFAULT_PERIOD = "1y"  # comfortably more than the 78 bars Ichimoku needs
DEFAULT_BATCH_SIZE = 100


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.rename(columns={c: str(c).capitalize() for c in frame.columns})
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"missing OHLC columns: {missing}")
    frame = frame[REQUIRED_COLUMNS].copy()
    frame.index = pd.to_datetime(frame.index)
    if getattr(frame.index, "tz", None) is not None:
        frame.index = frame.index.tz_localize(None)
    return frame.sort_index().dropna(how="all")


def _chunks(items: list[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def to_yahoo_ticker(symbol: str) -> str:
    return symbol if symbol.endswith(".NS") else f"{symbol}.NS"


def fetch_yahoo_batch(
    symbols: Iterable[str],
    period: str = DEFAULT_PERIOD,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, pd.DataFrame]:
    """Download daily OHLC for many NSE symbols, keyed by plain symbol.

    Symbols Yahoo has no data for are simply absent from the result.
    """
    import yfinance as yf  # imported lazily so offline use needs no network stack

    symbols = list(symbols)
    result: dict[str, pd.DataFrame] = {}

    for batch_number, batch in enumerate(_chunks(symbols, batch_size), start=1):
        tickers = [to_yahoo_ticker(s) for s in batch]
        log.info(
            "downloading batch %d (%d symbols)", batch_number, len(tickers)
        )
        try:
            raw = yf.download(
                tickers,
                period=period,
                interval="1d",
                auto_adjust=False,
                progress=False,
                group_by="ticker",
                threads=True,
            )
        except Exception as exc:
            log.warning("batch %d failed: %s", batch_number, exc)
            continue
        if raw is None or raw.empty:
            log.warning("batch %d returned no data", batch_number)
            continue

        for symbol, ticker in zip(batch, tickers):
            try:
                frame = raw[ticker] if isinstance(raw.columns, pd.MultiIndex) else raw
            except KeyError:
                continue
            frame = frame.dropna(how="all")
            if frame.empty:
                continue
            try:
                result[symbol] = _normalize(frame)
            except ValueError as exc:
                log.debug("skipping %s: %s", symbol, exc)

    return result


def load_csv_dir(symbols: Iterable[str], csv_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Load ``<csv_dir>/<SYMBOL>.csv`` files with Date + OHLC columns."""
    directory = Path(csv_dir)
    result: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        path = directory / f"{symbol}.csv"
        if not path.exists():
            log.debug("csv not found: %s", path)
            continue
        try:
            frame = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
            result[symbol] = _normalize(frame)
        except Exception as exc:
            log.warning("could not read %s: %s", path, exc)
    return result
