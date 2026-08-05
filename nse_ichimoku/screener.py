"""Run the Ichimoku position check across a set of symbols."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from .ichimoku import MIN_BARS, IchimokuReading, Position, read_latest

log = logging.getLogger(__name__)

#: NSE trades on Indian Standard Time, which has no daylight saving, so a
#: fixed offset is exact and needs no timezone database.
IST = timezone(timedelta(hours=5, minutes=30))


def ist_today() -> date:
    """Today's date in the exchange's own timezone."""
    return datetime.now(IST).date()


NO_PRICE_DATA = "no price data"
LAGGING_SESSION = "lagging the session"


@dataclass
class ScanResult:
    readings: list[IchimokuReading] = field(default_factory=list)
    #: Symbol -> why it could not be classified, so nothing vanishes silently.
    skipped: dict[str, str] = field(default_factory=dict)

    def by_position(self, position: Position) -> list[IchimokuReading]:
        return sorted(
            (r for r in self.readings if r.position is position),
            key=lambda r: r.symbol,
        )

    @property
    def above(self) -> list[IchimokuReading]:
        return self.by_position(Position.ABOVE)

    @property
    def below(self) -> list[IchimokuReading]:
        return self.by_position(Position.BELOW)

    @property
    def mixed(self) -> list[IchimokuReading]:
        return self.by_position(Position.MIXED)

    @property
    def as_of(self) -> pd.Timestamp | None:
        """The trading session this scan represents.

        Taken as the most common last-bar date across the universe rather
        than the maximum: a single ticker carrying an early or stray bar
        should not redefine which session the market as a whole closed on.
        """
        if not self.readings:
            return None
        dates = pd.Series([r.date for r in self.readings])
        return pd.Timestamp(dates.mode().iloc[0])

    @property
    def stale(self) -> list[IchimokuReading]:
        """Readings whose last bar predates the session the scan is for."""
        as_of = self.as_of
        if as_of is None:
            return []
        return sorted(
            (r for r in self.readings if r.date < as_of), key=lambda r: r.symbol
        )

    def drop_stale(self) -> ScanResult:
        """A copy holding only symbols that traded in the ``as_of`` session."""
        as_of = self.as_of
        if as_of is None:
            return self
        return ScanResult(
            readings=[r for r in self.readings if r.date >= as_of],
            skipped={
                **self.skipped,
                **{r.symbol: LAGGING_SESSION for r in self.stale},
            },
        )


def skip_reason(frame: pd.DataFrame) -> str:
    """Explain, in the report's terms, why a frame yielded no reading."""
    missing = {"High", "Low", "Close"} - set(frame.columns)
    if missing:
        return f"missing columns: {', '.join(sorted(missing))}"
    usable = len(frame.dropna(subset=["High", "Low", "Close"]))
    if usable < MIN_BARS:
        return f"insufficient history: {usable} of {MIN_BARS} daily bars"
    return "incomplete Ichimoku values at the latest bar"


def scan(price_data: dict[str, pd.DataFrame]) -> ScanResult:
    """Classify every symbol whose data supports a complete Ichimoku read."""
    result = ScanResult()
    for symbol in sorted(price_data):
        frame = price_data[symbol]
        try:
            reading = read_latest(symbol, frame)
        except Exception as exc:
            log.warning("failed to evaluate %s: %s", symbol, exc)
            result.skipped[symbol] = f"evaluation error: {exc}"
            continue
        if reading is None:
            result.skipped[symbol] = skip_reason(frame)
        else:
            result.readings.append(reading)
    return result
