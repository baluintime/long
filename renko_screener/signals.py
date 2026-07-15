"""Three-layer entry signal logic (PRD v2.0, section 3).

Layer 1 (structural trend): latest Renko brick is green, closes above the
Kumo, Tenkan > Kijun, and the Chikou Span is clear.
Layer 2 (money flow): CMF(21) on daily candles must exceed +0.05.
Layer 3 (exhaustion): RSI(14) on daily candles must be below 75.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass

import pandas as pd

from . import ichimoku as ichi
from . import indicators as ind
from .renko import bricks_to_frame, build_renko, round_brick_size

CMF_THRESHOLD = 0.05
RSI_OVERBOUGHT = 75.0


class Signal(str, enum.Enum):
    ENTER_LONG = "ENTER LONG"
    HOLD_RSI_EXHAUSTION = "HOLD-RSI EXHAUSTION"
    HOLD_LOW_VOLUME = "HOLD-LOW VOLUME"
    NO_TRADE = "NO TRADE"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


@dataclass(frozen=True)
class ScreenerRow:
    """One line of the EOD report (PRD v2.0, section 4)."""

    symbol: str
    brick_size: float  # ATR(14)-normalized brick size, INR
    cmf_value: float  # CMF(21)
    rsi_value: float  # RSI(14)
    signal: Signal
    bull_age_days: int | None  # days since the initial breakout
    kijun_level: float | None  # trailing stop-loss, INR


def _layer1_flags(brick_frame: pd.DataFrame) -> pd.Series:
    """Per-brick boolean: structural-trend (Layer 1) conditions all hold."""
    computed = ichi.compute_ichimoku(brick_frame)
    kumo_top = computed[["senkou_a", "senkou_b"]].max(axis=1)
    flags = (
        (computed["direction"] > 0)
        & (computed["close"] > kumo_top)
        & (computed["tenkan"] > computed["kijun"])
        & (computed["close"] > computed["chikou_ref"])
    )
    # Rows with incomplete Ichimoku values can never signal.
    complete = computed[["tenkan", "kijun", "senkou_a", "senkou_b", "chikou_ref"]].notna().all(axis=1)
    return flags & complete


def _bull_age_days(
    brick_frame: pd.DataFrame, layer1: pd.Series, report_date: pd.Timestamp
) -> int | None:
    """Calendar days since the first brick of the current Layer-1 streak."""
    if layer1.empty or not bool(layer1.iloc[-1]):
        return None
    idx = len(layer1) - 1
    while idx > 0 and bool(layer1.iloc[idx - 1]):
        idx -= 1
    breakout_date = pd.Timestamp(brick_frame["date"].iloc[idx])
    return max((pd.Timestamp(report_date).normalize() - breakout_date.normalize()).days, 0)


def evaluate_symbol(symbol: str, ohlcv: pd.DataFrame) -> ScreenerRow:
    """Run the 3-step verification checklist on one symbol's daily OHLCV.

    ``ohlcv`` must be date-indexed (ascending) with columns
    Open/High/Low/Close/Volume.
    """
    ohlcv = ohlcv.dropna(subset=["Open", "High", "Low", "Close"]).sort_index()

    def no_trade(brick: float = math.nan, cmf_v: float = math.nan, rsi_v: float = math.nan) -> ScreenerRow:
        return ScreenerRow(symbol, brick, cmf_v, rsi_v, Signal.NO_TRADE, None, None)

    if len(ohlcv) < ind.CMF_PERIOD + 1:
        return no_trade()

    atr_series = ind.atr(ohlcv["High"], ohlcv["Low"], ohlcv["Close"])
    brick_size = round_brick_size(float(atr_series.iloc[-1]))
    cmf_value = float(ind.cmf(ohlcv["High"], ohlcv["Low"], ohlcv["Close"], ohlcv["Volume"]).iloc[-1])
    rsi_value = float(ind.rsi(ohlcv["Close"]).iloc[-1])

    if not math.isfinite(brick_size) or not math.isfinite(cmf_value) or not math.isfinite(rsi_value):
        return no_trade(brick_size, cmf_value, rsi_value)

    bricks = build_renko(ohlcv["Close"], brick_size)
    if len(bricks) < ichi.MIN_BRICKS:
        return no_trade(brick_size, cmf_value, rsi_value)

    brick_frame = bricks_to_frame(bricks)
    state = ichi.latest_state(brick_frame)
    if state is None:
        return no_trade(brick_size, cmf_value, rsi_value)

    layer1 = _layer1_flags(brick_frame)
    if not bool(layer1.iloc[-1]):
        return ScreenerRow(
            symbol, brick_size, cmf_value, rsi_value, Signal.NO_TRADE, None, state.kijun
        )

    bull_age = _bull_age_days(brick_frame, layer1, ohlcv.index[-1])

    if cmf_value <= CMF_THRESHOLD:
        signal = Signal.HOLD_LOW_VOLUME
    elif rsi_value >= RSI_OVERBOUGHT:
        signal = Signal.HOLD_RSI_EXHAUSTION
    else:
        signal = Signal.ENTER_LONG

    return ScreenerRow(symbol, brick_size, cmf_value, rsi_value, signal, bull_age, state.kijun)
