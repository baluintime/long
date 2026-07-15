"""ATR-normalized Renko brick construction.

Bricks are built from daily closing prices with a fixed brick size equal to
the latest daily ATR(14) at scan time ("volatility-normalized"). A new brick
in the trend direction forms per full brick size of movement; a reversal
requires two brick sizes of adverse movement (classic Renko).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Brick:
    date: pd.Timestamp  # date of the daily candle that completed the brick
    open: float
    close: float
    direction: int  # +1 green (up), -1 red (down)

    @property
    def high(self) -> float:
        return max(self.open, self.close)

    @property
    def low(self) -> float:
        return min(self.open, self.close)

    @property
    def is_green(self) -> bool:
        return self.direction > 0


def build_renko(closes: pd.Series, brick_size: float) -> list[Brick]:
    """Build close-based Renko bricks from a date-indexed close series."""
    if brick_size <= 0:
        raise ValueError(f"brick_size must be positive, got {brick_size}")
    closes = closes.dropna()
    if closes.empty:
        return []

    bricks: list[Brick] = []
    # Anchor the first brick boundary on the first close.
    anchor = closes.iloc[0]
    up_level = anchor  # top of the last brick
    down_level = anchor  # bottom of the last brick

    for date, price in closes.items():
        while True:
            direction = bricks[-1].direction if bricks else 0
            if direction >= 0 and price >= up_level + brick_size:
                new_close = up_level + brick_size
                bricks.append(Brick(date, up_level, new_close, +1))
                down_level = up_level
                up_level = new_close
            elif direction <= 0 and price <= down_level - brick_size:
                new_close = down_level - brick_size
                bricks.append(Brick(date, down_level, new_close, -1))
                up_level = down_level
                down_level = new_close
            elif direction > 0 and price <= up_level - 2 * brick_size:
                # Reversal down: skip the shared level, open at the previous
                # brick's bottom.
                new_close = down_level - brick_size
                bricks.append(Brick(date, down_level, new_close, -1))
                up_level = down_level
                down_level = new_close
            elif direction < 0 and price >= down_level + 2 * brick_size:
                # Reversal up.
                new_close = up_level + brick_size
                bricks.append(Brick(date, up_level, new_close, +1))
                down_level = up_level
                up_level = new_close
            else:
                break
    return bricks


def bricks_to_frame(bricks: list[Brick]) -> pd.DataFrame:
    """Convert bricks to a DataFrame with open/high/low/close/direction/date."""
    return pd.DataFrame(
        {
            "date": [b.date for b in bricks],
            "open": [b.open for b in bricks],
            "high": [b.high for b in bricks],
            "low": [b.low for b in bricks],
            "close": [b.close for b in bricks],
            "direction": [b.direction for b in bricks],
        }
    )


def round_brick_size(size: float) -> float:
    """Round the ATR brick size to a sane tick (2 decimals, min 0.05 INR)."""
    if not math.isfinite(size) or size <= 0:
        return float("nan")
    return max(round(size, 2), 0.05)
