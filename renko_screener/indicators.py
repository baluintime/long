"""Time-based candlestick indicators: ATR, RSI, CMF.

All functions take pandas Series/DataFrames indexed by date and return
Series aligned to the same index. Wilder smoothing is used for ATR and RSI,
matching standard charting-platform values.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ATR_PERIOD = 14
RSI_PERIOD = 14
CMF_PERIOD = 21


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    # First bar has no previous close; true range is just high - low.
    tr.iloc[0] = high.iloc[0] - low.iloc[0]
    return tr


def atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = ATR_PERIOD
) -> pd.Series:
    """Average True Range with Wilder smoothing."""
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Relative Strength Index with Wilder smoothing."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    out = 100.0 - 100.0 / (1.0 + rs)
    # Flat-loss windows produce inf RS -> RSI 100.
    out = out.where(avg_loss != 0.0, 100.0)
    out[avg_gain.isna() | avg_loss.isna()] = np.nan
    return out


def cmf(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = CMF_PERIOD,
) -> pd.Series:
    """Chaikin Money Flow over ``period`` bars.

    CMF = sum(Money Flow Volume, n) / sum(Volume, n) where
    MFV = Volume * ((Close - Low) - (High - Close)) / (High - Low).
    """
    hl_range = high - low
    mfm = ((close - low) - (high - close)) / hl_range.replace(0.0, np.nan)
    mfm = mfm.fillna(0.0)  # doji / limit-locked bars contribute zero flow
    mfv = mfm * volume
    vol_sum = volume.rolling(period, min_periods=period).sum()
    return mfv.rolling(period, min_periods=period).sum() / vol_sum.replace(0.0, np.nan)
