"""Ichimoku Kinko Hyo computed on the Renko brick series.

The PRD's Layer-1 condition ("green brick closes above Kumo, Tenkan > Kijun,
Chikou Span clear") is evaluated in brick space: each Renko brick is treated
as one Ichimoku period. Standard 9/26/52 parameters.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

TENKAN_PERIOD = 9
KIJUN_PERIOD = 26
SENKOU_B_PERIOD = 52
DISPLACEMENT = 26

# Bricks needed for a fully-formed cloud at the latest brick:
# Senkou B needs 52 bricks, displaced 26 forward.
MIN_BRICKS = SENKOU_B_PERIOD + DISPLACEMENT


@dataclass(frozen=True)
class IchimokuState:
    tenkan: float
    kijun: float
    senkou_a: float  # cloud edge at the current brick
    senkou_b: float
    chikou_reference: float  # brick close DISPLACEMENT bricks back

    @property
    def kumo_top(self) -> float:
        return max(self.senkou_a, self.senkou_b)

    @property
    def kumo_bottom(self) -> float:
        return min(self.senkou_a, self.senkou_b)


def _midpoint(high: pd.Series, low: pd.Series, period: int) -> pd.Series:
    return (
        high.rolling(period, min_periods=period).max()
        + low.rolling(period, min_periods=period).min()
    ) / 2.0


def compute_ichimoku(brick_frame: pd.DataFrame) -> pd.DataFrame:
    """Add tenkan/kijun/senkou_a/senkou_b/chikou_ref columns to a brick frame.

    ``senkou_a``/``senkou_b`` at row *i* are the cloud values in effect at
    brick *i*, i.e. computed from data ``DISPLACEMENT`` bricks earlier.
    """
    high, low, close = brick_frame["high"], brick_frame["low"], brick_frame["close"]
    out = brick_frame.copy()
    out["tenkan"] = _midpoint(high, low, TENKAN_PERIOD)
    out["kijun"] = _midpoint(high, low, KIJUN_PERIOD)
    senkou_a_raw = (out["tenkan"] + out["kijun"]) / 2.0
    senkou_b_raw = _midpoint(high, low, SENKOU_B_PERIOD)
    out["senkou_a"] = senkou_a_raw.shift(DISPLACEMENT)
    out["senkou_b"] = senkou_b_raw.shift(DISPLACEMENT)
    out["chikou_ref"] = close.shift(DISPLACEMENT)
    return out


def latest_state(brick_frame: pd.DataFrame) -> IchimokuState | None:
    """Ichimoku state at the most recent brick, or None if not enough bricks."""
    if len(brick_frame) < MIN_BRICKS:
        return None
    computed = compute_ichimoku(brick_frame)
    row = computed.iloc[-1]
    if row[["tenkan", "kijun", "senkou_a", "senkou_b", "chikou_ref"]].isna().any():
        return None
    return IchimokuState(
        tenkan=float(row["tenkan"]),
        kijun=float(row["kijun"]),
        senkou_a=float(row["senkou_a"]),
        senkou_b=float(row["senkou_b"]),
        chikou_reference=float(row["chikou_ref"]),
    )
