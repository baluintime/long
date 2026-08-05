"""Ichimoku Kinko Hyo computation and close-vs-lines classification.

Standard settings: Tenkan-sen 9, Kijun-sen 26, Senkou Span B 52, with the
cloud displaced 26 bars forward and the Chikou Span 26 bars back.

A stock is ABOVE when its latest close is greater than *every* Ichimoku
line plotted at that bar (Tenkan, Kijun, Senkou A, Senkou B), and BELOW
when it is less than every one of them. Anything else is MIXED.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass

import pandas as pd

TENKAN_PERIOD = 9
KIJUN_PERIOD = 26
SENKOU_B_PERIOD = 52
DISPLACEMENT = 26

#: Minimum daily bars for a fully-formed cloud at the latest bar.
MIN_BARS = SENKOU_B_PERIOD + DISPLACEMENT

LINE_NAMES = ("tenkan", "kijun", "senkou_a", "senkou_b")

#: Levels the close is measured against as a percentage. The two cloud
#: edges are derived from Senkou A/B but are what a trader actually reads.
DISTANCE_TARGETS = (*LINE_NAMES, "cloud_top", "cloud_bottom")


def percent_gap(close: float, level: float) -> float:
    """Signed distance from ``level`` to ``close``, in percent of the level.

    Positive means the close sits above the level. Returns NaN for a level
    that cannot anchor a percentage.
    """
    if not math.isfinite(level) or not math.isfinite(close) or level <= 0:
        return float("nan")
    return (close - level) / level * 100.0


class Position(str, enum.Enum):
    ABOVE = "ABOVE"  # close above every Ichimoku line
    BELOW = "BELOW"  # close below every Ichimoku line
    MIXED = "MIXED"  # close tangled in the lines / inside the cloud

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


@dataclass(frozen=True)
class IchimokuReading:
    """Latest-bar Ichimoku values and the resulting classification."""

    symbol: str
    date: pd.Timestamp
    close: float
    tenkan: float
    kijun: float
    senkou_a: float
    senkou_b: float
    position: Position
    chikou_clear: bool  # close is above (ABOVE) / below (BELOW) the price 26 bars back

    @property
    def cloud_top(self) -> float:
        return max(self.senkou_a, self.senkou_b)

    @property
    def cloud_bottom(self) -> float:
        return min(self.senkou_a, self.senkou_b)

    @property
    def percent_gaps(self) -> dict[str, float]:
        """How far the close sits from each level, in percent."""
        return {
            name: percent_gap(self.close, getattr(self, name))
            for name in DISTANCE_TARGETS
        }

    @property
    def percent_to_nearest_line(self) -> float:
        """Signed gap to whichever of the four lines the close is nearest.

        For an ABOVE stock this is the cushion before it breaks back into
        the lines; for a BELOW stock, how far it must rally to reach them.
        """
        gaps = [
            percent_gap(self.close, getattr(self, name))
            for name in LINE_NAMES
            if math.isfinite(getattr(self, name))
        ]
        gaps = [g for g in gaps if math.isfinite(g)]
        return min(gaps, key=abs) if gaps else float("nan")


def _midpoint(high: pd.Series, low: pd.Series, period: int) -> pd.Series:
    """(highest high + lowest low) / 2 over ``period`` bars."""
    return (
        high.rolling(period, min_periods=period).max()
        + low.rolling(period, min_periods=period).min()
    ) / 2.0


def compute_ichimoku(ohlc: pd.DataFrame) -> pd.DataFrame:
    """Return ``ohlc`` with Ichimoku columns added.

    ``senkou_a``/``senkou_b`` at row *i* are the cloud values *in effect* at
    bar *i* (computed ``DISPLACEMENT`` bars earlier and projected forward),
    so they can be compared directly against that bar's close.
    """
    high, low, close = ohlc["High"], ohlc["Low"], ohlc["Close"]
    out = ohlc.copy()
    out["tenkan"] = _midpoint(high, low, TENKAN_PERIOD)
    out["kijun"] = _midpoint(high, low, KIJUN_PERIOD)
    out["senkou_a"] = ((out["tenkan"] + out["kijun"]) / 2.0).shift(DISPLACEMENT)
    out["senkou_b"] = _midpoint(high, low, SENKOU_B_PERIOD).shift(DISPLACEMENT)
    out["chikou_ref"] = close.shift(DISPLACEMENT)
    return out


def classify(close: float, lines: dict[str, float]) -> Position:
    """Classify a close against the four Ichimoku lines at the same bar."""
    values = [lines[name] for name in LINE_NAMES]
    if all(close > value for value in values):
        return Position.ABOVE
    if all(close < value for value in values):
        return Position.BELOW
    return Position.MIXED


def read_latest(symbol: str, ohlc: pd.DataFrame) -> IchimokuReading | None:
    """Ichimoku reading for the most recent bar, or None if unavailable.

    Returns None when there is too little history for a fully-formed cloud
    or the data contains gaps that leave the latest lines undefined.
    """
    if not {"High", "Low", "Close"}.issubset(ohlc.columns):
        return None
    ohlc = ohlc.dropna(subset=["High", "Low", "Close"]).sort_index()
    if len(ohlc) < MIN_BARS:
        return None

    computed = compute_ichimoku(ohlc)
    row = computed.iloc[-1]
    if row[list(LINE_NAMES)].isna().any():
        return None

    close = float(row["Close"])
    lines = {name: float(row[name]) for name in LINE_NAMES}
    position = classify(close, lines)

    chikou_ref = row["chikou_ref"]
    if pd.isna(chikou_ref):
        chikou_clear = False
    elif position is Position.ABOVE:
        chikou_clear = close > float(chikou_ref)
    elif position is Position.BELOW:
        chikou_clear = close < float(chikou_ref)
    else:
        chikou_clear = False

    return IchimokuReading(
        symbol=symbol,
        date=pd.Timestamp(computed.index[-1]),
        close=close,
        position=position,
        chikou_clear=chikou_clear,
        **lines,
    )
