import numpy as np
import pandas as pd
import pytest

from renko_screener.renko import build_renko, bricks_to_frame, round_brick_size


def _series(values) -> pd.Series:
    return pd.Series(
        list(values), index=pd.bdate_range("2025-01-01", periods=len(list(values))), dtype=float
    )


def test_steady_uptrend_produces_green_bricks():
    closes = _series(np.arange(100, 150, 1.0))
    bricks = build_renko(closes, brick_size=5.0)
    assert len(bricks) == 9  # (149 - 100) // 5
    assert all(b.is_green for b in bricks)
    assert bricks[0].open == 100.0 and bricks[0].close == 105.0
    assert bricks[-1].close == 145.0


def test_steady_downtrend_produces_red_bricks():
    closes = _series(np.arange(150, 100, -1.0))
    bricks = build_renko(closes, brick_size=5.0)
    assert len(bricks) == 9
    assert all(not b.is_green for b in bricks)
    assert bricks[-1].close == 105.0


def test_reversal_requires_two_brick_sizes():
    # Rise 100 -> 110 (two up bricks of 5), then pull back to 104:
    # only 6 points against the trend -> no reversal brick yet.
    closes = _series([100, 105, 110, 104])
    bricks = build_renko(closes, brick_size=5.0)
    assert [b.direction for b in bricks] == [1, 1]

    # Extend the pullback to 99 (>= 2 bricks below the top): reversal forms.
    closes = _series([100, 105, 110, 99])
    bricks = build_renko(closes, brick_size=5.0)
    assert [b.direction for b in bricks] == [1, 1, -1]
    assert bricks[-1].open == 105.0 and bricks[-1].close == 100.0


def test_sideways_market_produces_no_bricks():
    closes = _series([100, 101, 100, 102, 101, 100])
    assert build_renko(closes, brick_size=5.0) == []


def test_large_gap_produces_multiple_bricks_same_day():
    closes = _series([100, 121])
    bricks = build_renko(closes, brick_size=5.0)
    assert len(bricks) == 4
    assert all(b.date == closes.index[1] for b in bricks)
    assert bricks[-1].close == 120.0


def test_bricks_to_frame_columns():
    closes = _series(np.arange(100, 130, 1.0))
    frame = bricks_to_frame(build_renko(closes, brick_size=5.0))
    assert list(frame.columns) == ["date", "open", "high", "low", "close", "direction"]
    assert (frame["high"] >= frame["low"]).all()


def test_invalid_brick_size_raises():
    with pytest.raises(ValueError):
        build_renko(_series([100, 105]), brick_size=0.0)


def test_round_brick_size():
    assert round_brick_size(12.3456) == 12.35
    assert round_brick_size(0.001) == 0.05  # floor at one NSE tick
    assert np.isnan(round_brick_size(float("nan")))
    assert np.isnan(round_brick_size(-1.0))
