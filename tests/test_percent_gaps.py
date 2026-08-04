"""Percentage distance between the close and each Ichimoku line."""

import math

import numpy as np
import pandas as pd
import pytest

from nse_ichimoku import report
from nse_ichimoku.ichimoku import IchimokuReading, Position, percent_gap, read_latest


def _reading(close: float, tenkan, kijun, senkou_a, senkou_b) -> IchimokuReading:
    return IchimokuReading(
        symbol="TEST",
        date=pd.Timestamp("2026-08-04"),
        close=close,
        tenkan=tenkan,
        kijun=kijun,
        senkou_a=senkou_a,
        senkou_b=senkou_b,
        position=Position.ABOVE,
        chikou_clear=True,
    )


def test_percent_gap_above_is_positive():
    assert percent_gap(110.0, 100.0) == pytest.approx(10.0)


def test_percent_gap_below_is_negative():
    assert percent_gap(90.0, 100.0) == pytest.approx(-10.0)


def test_percent_gap_on_the_line_is_zero():
    assert percent_gap(100.0, 100.0) == pytest.approx(0.0)


def test_percent_gap_is_relative_to_the_line():
    # 5 points above a 50 line is twice the percentage of 5 above a 100 line.
    assert percent_gap(55.0, 50.0) == pytest.approx(10.0)
    assert percent_gap(105.0, 100.0) == pytest.approx(5.0)


@pytest.mark.parametrize("level", [0.0, -10.0, float("nan"), float("inf")])
def test_percent_gap_rejects_unusable_levels(level):
    assert math.isnan(percent_gap(100.0, level))


def test_percent_gaps_cover_every_line_and_cloud_edge():
    reading = _reading(110.0, tenkan=100.0, kijun=100.0, senkou_a=50.0, senkou_b=55.0)
    gaps = reading.percent_gaps
    assert gaps["tenkan"] == pytest.approx(10.0)
    assert gaps["kijun"] == pytest.approx(10.0)
    assert gaps["senkou_a"] == pytest.approx(120.0)
    assert gaps["senkou_b"] == pytest.approx(100.0)
    # Cloud top is the higher of Senkou A/B, here 55.
    assert gaps["cloud_top"] == pytest.approx(100.0)
    assert gaps["cloud_bottom"] == pytest.approx(120.0)


def test_percent_to_nearest_line_is_the_smallest_cushion_when_above():
    reading = _reading(110.0, tenkan=100.0, kijun=90.0, senkou_a=80.0, senkou_b=70.0)
    # Tenkan is nearest: +10%.
    assert reading.percent_to_nearest_line == pytest.approx(10.0)


def test_percent_to_nearest_line_is_signed_when_below():
    reading = _reading(90.0, tenkan=100.0, kijun=110.0, senkou_a=120.0, senkou_b=130.0)
    assert reading.percent_to_nearest_line == pytest.approx(-10.0)


def test_percent_to_nearest_line_picks_smallest_magnitude_when_mixed():
    # Close sits between the lines; the nearest is Kijun 2% below it.
    reading = _reading(102.0, tenkan=110.0, kijun=100.0, senkou_a=105.0, senkou_b=95.0)
    assert reading.percent_to_nearest_line == pytest.approx(2.0)


def test_frame_carries_every_percentage_column():
    frame = report.readings_to_frame(
        [_reading(110.0, tenkan=100.0, kijun=100.0, senkou_a=50.0, senkou_b=55.0)]
    )
    assert list(frame.columns) == report.DETAIL_COLUMNS
    row = frame.iloc[0]
    assert row["% vs Tenkan"] == pytest.approx(10.0)
    assert row["% vs Senkou A"] == pytest.approx(120.0)
    assert row["% vs Cloud Top"] == pytest.approx(100.0)
    assert row["% to Nearest Line"] == pytest.approx(10.0)
    assert row["Cloud Top"] == pytest.approx(55.0)
    assert row["Cloud Bottom"] == pytest.approx(50.0)


def test_percentages_are_consistent_with_a_real_scan():
    closes = np.arange(100, 300, dtype=float)
    ohlc = pd.DataFrame(
        {"Open": closes, "High": closes + 0.5, "Low": closes - 0.5, "Close": closes},
        index=pd.bdate_range("2024-01-01", periods=len(closes)),
    )
    reading = read_latest("UP", ohlc)
    gaps = reading.percent_gaps
    # Recompute independently from the reported levels.
    assert gaps["kijun"] == pytest.approx(
        (reading.close - reading.kijun) / reading.kijun * 100
    )
    # A steady uptrend sits above every line, so every gap is positive.
    assert all(value > 0 for value in gaps.values())


def test_console_table_shows_percentages():
    from nse_ichimoku.screener import ScanResult

    result = ScanResult(
        readings=[_reading(110.0, tenkan=100.0, kijun=100.0, senkou_a=50.0, senkou_b=55.0)]
    )
    text = report.render_detail(result)
    assert "% vs Tenkan" in text and "% to Nearest Line" in text
