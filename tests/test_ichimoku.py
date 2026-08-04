import numpy as np
import pandas as pd
import pytest

from nse_ichimoku.ichimoku import (
    DISPLACEMENT,
    KIJUN_PERIOD,
    MIN_BARS,
    TENKAN_PERIOD,
    Position,
    classify,
    compute_ichimoku,
    read_latest,
)


def _ohlc(closes, spread: float = 0.5) -> pd.DataFrame:
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes + spread,
            "Low": closes - spread,
            "Close": closes,
        },
        index=pd.bdate_range("2024-01-01", periods=len(closes)),
    )


def test_classify_above_requires_every_line():
    lines = {"tenkan": 90.0, "kijun": 85.0, "senkou_a": 80.0, "senkou_b": 75.0}
    assert classify(100.0, lines) is Position.ABOVE
    # One line above the close is enough to disqualify it.
    assert classify(88.0, lines) is Position.MIXED


def test_classify_below_requires_every_line():
    lines = {"tenkan": 90.0, "kijun": 95.0, "senkou_a": 100.0, "senkou_b": 105.0}
    assert classify(80.0, lines) is Position.BELOW
    assert classify(92.0, lines) is Position.MIXED


def test_classify_inside_cloud_is_mixed():
    lines = {"tenkan": 98.0, "kijun": 96.0, "senkou_a": 105.0, "senkou_b": 95.0}
    assert classify(100.0, lines) is Position.MIXED


def test_classify_on_a_line_is_mixed():
    lines = {"tenkan": 100.0, "kijun": 90.0, "senkou_a": 80.0, "senkou_b": 70.0}
    assert classify(100.0, lines) is Position.MIXED


def test_tenkan_and_kijun_are_period_midpoints():
    closes = np.arange(100, 200, dtype=float)
    frame = _ohlc(closes, spread=0.0)
    computed = compute_ichimoku(frame)
    last = computed.iloc[-1]
    window_high, window_low = closes[-1], closes[-TENKAN_PERIOD]
    assert last["tenkan"] == pytest.approx((window_high + window_low) / 2)
    assert last["kijun"] == pytest.approx((closes[-1] + closes[-KIJUN_PERIOD]) / 2)


def test_cloud_is_displaced_forward():
    closes = np.arange(100, 250, dtype=float)
    computed = compute_ichimoku(_ohlc(closes, spread=0.0))
    # Senkou B in effect now was computed DISPLACEMENT bars ago.
    raw_senkou_b = (
        computed["High"].rolling(52).max() + computed["Low"].rolling(52).min()
    ) / 2
    assert computed["senkou_b"].iloc[-1] == pytest.approx(
        raw_senkou_b.iloc[-1 - DISPLACEMENT]
    )


def test_read_latest_uptrend_is_above():
    reading = read_latest("UP", _ohlc(np.arange(100, 300, dtype=float)))
    assert reading is not None
    assert reading.position is Position.ABOVE
    assert reading.close > reading.cloud_top
    assert reading.chikou_clear is True


def test_read_latest_downtrend_is_below():
    reading = read_latest("DOWN", _ohlc(np.arange(300, 100, -1, dtype=float)))
    assert reading is not None
    assert reading.position is Position.BELOW
    assert reading.close < reading.cloud_bottom
    assert reading.chikou_clear is True


def test_read_latest_flat_market_is_mixed():
    closes = 100 + 0.5 * np.sin(np.linspace(0, 12, 200))
    reading = read_latest("FLAT", _ohlc(closes))
    assert reading is not None
    assert reading.position is Position.MIXED


def test_read_latest_needs_full_cloud():
    assert read_latest("SHORT", _ohlc(np.arange(100, 100 + MIN_BARS - 1.0))) is None
    assert read_latest("OK", _ohlc(np.arange(100, 100 + MIN_BARS * 1.0))) is not None


def test_read_latest_ignores_leading_gaps():
    closes = np.arange(100, 300, dtype=float)
    frame = _ohlc(closes)
    frame.iloc[:5, :] = np.nan  # missing bars at the start of the series
    reading = read_latest("GAPPY", frame)
    assert reading is not None
    assert reading.position is Position.ABOVE
