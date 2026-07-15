import numpy as np
import pandas as pd
import pytest

from renko_screener import indicators as ind


def _dates(n: int) -> pd.DatetimeIndex:
    return pd.bdate_range("2025-01-01", periods=n)


def test_rsi_all_gains_is_100():
    close = pd.Series(np.arange(1, 41, dtype=float), index=_dates(40))
    value = ind.rsi(close).iloc[-1]
    assert value == pytest.approx(100.0)


def test_rsi_all_losses_is_0():
    close = pd.Series(np.arange(200, 120, -2, dtype=float), index=_dates(40))
    value = ind.rsi(close).iloc[-1]
    assert value == pytest.approx(0.0, abs=1e-9)


def test_rsi_alternating_moves_near_50():
    # Equal-magnitude alternating gains/losses -> RSI hovers around 50.
    moves = np.tile([1.0, -1.0], 50)
    close = pd.Series(100 + np.cumsum(moves), index=_dates(100))
    value = ind.rsi(close).iloc[-1]
    assert 40 < value < 60


def test_rsi_nan_before_period():
    close = pd.Series(np.linspace(100, 110, 30), index=_dates(30))
    series = ind.rsi(close, period=14)
    assert series.iloc[:13].isna().all()
    assert series.iloc[14:].notna().all()


def test_atr_constant_range():
    # Bars with a constant 2-point range and no gaps: ATR converges to 2.
    n = 200
    close = pd.Series(np.full(n, 100.0), index=_dates(n))
    high = close + 1
    low = close - 1
    value = ind.atr(high, low, close).iloc[-1]
    assert value == pytest.approx(2.0, rel=1e-6)


def test_cmf_close_at_high_is_positive_one():
    # Close pinned at the high with equal volume -> CMF = +1.
    n = 60
    idx = _dates(n)
    low = pd.Series(np.full(n, 99.0), index=idx)
    high = pd.Series(np.full(n, 101.0), index=idx)
    close = high.copy()
    volume = pd.Series(np.full(n, 1000.0), index=idx)
    value = ind.cmf(high, low, close, volume).iloc[-1]
    assert value == pytest.approx(1.0)


def test_cmf_close_at_low_is_negative_one():
    n = 60
    idx = _dates(n)
    low = pd.Series(np.full(n, 99.0), index=idx)
    high = pd.Series(np.full(n, 101.0), index=idx)
    close = low.copy()
    volume = pd.Series(np.full(n, 1000.0), index=idx)
    value = ind.cmf(high, low, close, volume).iloc[-1]
    assert value == pytest.approx(-1.0)


def test_cmf_midpoint_close_is_zero():
    n = 60
    idx = _dates(n)
    low = pd.Series(np.full(n, 99.0), index=idx)
    high = pd.Series(np.full(n, 101.0), index=idx)
    close = pd.Series(np.full(n, 100.0), index=idx)
    volume = pd.Series(np.full(n, 1000.0), index=idx)
    value = ind.cmf(high, low, close, volume).iloc[-1]
    assert value == pytest.approx(0.0, abs=1e-12)


def test_cmf_handles_zero_range_bars():
    # Limit-locked bars (high == low) must not divide by zero.
    n = 60
    idx = _dates(n)
    price = pd.Series(np.full(n, 100.0), index=idx)
    volume = pd.Series(np.full(n, 1000.0), index=idx)
    value = ind.cmf(price, price, price, volume).iloc[-1]
    assert value == pytest.approx(0.0)
