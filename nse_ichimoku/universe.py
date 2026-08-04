"""NSE listed-equity universe.

The full list of NSE-listed stocks comes from the exchange's own master
file, ``EQUITY_L.csv``. NSE serves it only to browser-like clients, so the
session first visits the site to pick up cookies before requesting the CSV.

Results are cached on disk (default: one day) so repeated scans do not
re-hit the exchange. If NSE is unreachable — an offline machine or a
network that blocks the exchange — the loader falls back to the bundled
snapshot in ``data/nse_equity_list.csv``, which covers the liquid names
only, and says so loudly.
"""

from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

EQUITY_LIST_URLS = (
    "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
    "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
)
NSE_HOME = "https://www.nseindia.com"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/csv,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{NSE_HOME}/market-data/securities-available-for-trading",
}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BUNDLED_FALLBACK = DATA_DIR / "nse_equity_list.csv"
CACHE_FILE = DATA_DIR / ".cache_equity_list.csv"
CACHE_MAX_AGE_SECONDS = 24 * 60 * 60

#: Series worth screening: EQ is the rolling-settlement equity segment,
#: BE the trade-for-trade segment. Everything else (debt, ETFs, warrants)
#: is not a stock in the sense this screener cares about.
DEFAULT_SERIES = ("EQ", "BE")


@dataclass(frozen=True)
class Universe:
    symbols: list[str]
    source: str  # "nse", "cache", "bundled" or "file"

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.symbols)


def _parse_equity_csv(text: str, series: tuple[str, ...] | None) -> list[str]:
    frame = pd.read_csv(io.StringIO(text))
    frame.columns = [c.strip().upper() for c in frame.columns]
    if "SYMBOL" not in frame.columns:
        raise ValueError("EQUITY_L.csv has no SYMBOL column")
    if series and "SERIES" in frame.columns:
        wanted = {s.upper() for s in series}
        frame = frame[frame["SERIES"].astype(str).str.strip().str.upper().isin(wanted)]
    symbols = (
        frame["SYMBOL"].astype(str).str.strip().str.upper().replace("", pd.NA).dropna()
    )
    return sorted(dict.fromkeys(symbols))


def _download_equity_csv(timeout: float = 30.0) -> str:
    import requests  # imported lazily so offline use needs no HTTP stack

    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    try:
        # Prime the session cookies; NSE rejects cold requests to the archive.
        session.get(NSE_HOME, timeout=timeout)
    except Exception as exc:
        log.debug("cookie priming failed (continuing anyway): %s", exc)

    errors = []
    for url in EQUITY_LIST_URLS:
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            if response.text.strip():
                return response.text
            errors.append(f"{url}: empty response")
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise ConnectionError("could not download NSE equity list — " + "; ".join(errors))


def _read_cache(max_age: float) -> str | None:
    if not CACHE_FILE.exists():
        return None
    age = time.time() - CACHE_FILE.stat().st_mtime
    if age > max_age:
        log.debug("cached equity list is stale (%.0fs old)", age)
        return None
    return CACHE_FILE.read_text()


def _write_cache(text: str) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(text)
    except OSError as exc:  # a read-only checkout must not break the scan
        log.debug("could not write cache: %s", exc)


def load_universe(
    path: str | Path | None = None,
    *,
    refresh: bool = False,
    allow_fallback: bool = True,
    series: tuple[str, ...] | None = DEFAULT_SERIES,
    cache_max_age: float = CACHE_MAX_AGE_SECONDS,
) -> Universe:
    """Load the NSE stock universe.

    ``path`` reads a local list instead of contacting NSE: either a plain
    text file of one symbol per line, or a CSV in EQUITY_L format.
    ``refresh`` ignores the on-disk cache. ``allow_fallback`` permits the
    bundled partial snapshot when NSE cannot be reached.
    """
    if path:
        file_path = Path(path)
        text = file_path.read_text()
        if file_path.suffix.lower() == ".csv":
            return Universe(_parse_equity_csv(text, series), "file")
        return Universe(_read_symbol_lines(text), "file")

    if not refresh:
        cached = _read_cache(cache_max_age)
        if cached:
            return Universe(_parse_equity_csv(cached, series), "cache")

    try:
        text = _download_equity_csv()
    except Exception as exc:
        if not allow_fallback:
            raise
        log.warning("NSE fetch failed (%s) — using bundled fallback list", exc)
        return Universe(
            _parse_equity_csv(BUNDLED_FALLBACK.read_text(), series), "bundled"
        )

    _write_cache(text)
    return Universe(_parse_equity_csv(text, series), "nse")


def _read_symbol_lines(text: str) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        symbol = raw.split("#", 1)[0].strip().upper()
        if symbol and symbol not in seen:
            seen.add(symbol)
            symbols.append(symbol)
    return symbols
