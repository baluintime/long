"""The once-a-day, post-close run must never pass stale data off as current."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from nse_ichimoku import report
from nse_ichimoku.ichimoku import Position
from nse_ichimoku.screener import ScanResult, ist_today, scan


def _ohlc(closes, end: str) -> pd.DataFrame:
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes + 0.5,
            "Low": closes - 0.5,
            "Close": closes,
        },
        index=pd.bdate_range(end=end, periods=len(closes)),
    )


def _uptrend(end: str) -> pd.DataFrame:
    return _ohlc(np.arange(100, 300, dtype=float), end)


def _downtrend(end: str) -> pd.DataFrame:
    return _ohlc(np.arange(300, 100, -1, dtype=float), end)


def test_as_of_is_the_session_shared_by_the_market():
    result = scan(
        {
            "AAA": _uptrend("2026-08-04"),
            "BBB": _uptrend("2026-08-04"),
            "CCC": _downtrend("2026-08-04"),
            "SUSPENDED": _downtrend("2026-07-20"),  # halted: last bar is old
        }
    )
    assert result.as_of == pd.Timestamp("2026-08-04")


def test_as_of_ignores_a_single_stray_future_bar():
    # One ticker carrying a stray bar must not redefine the session.
    result = scan(
        {
            "AAA": _uptrend("2026-08-04"),
            "BBB": _uptrend("2026-08-04"),
            "STRAY": _uptrend("2026-08-05"),
        }
    )
    assert result.as_of == pd.Timestamp("2026-08-04")


def test_as_of_is_none_without_readings():
    assert ScanResult().as_of is None


def test_stale_lists_symbols_behind_the_session():
    result = scan(
        {
            "FRESH": _uptrend("2026-08-04"),
            "ALSOFRESH": _uptrend("2026-08-04"),
            "SUSPENDED": _downtrend("2026-07-20"),
        }
    )
    assert [r.symbol for r in result.stale] == ["SUSPENDED"]


def test_drop_stale_moves_laggards_to_skipped():
    result = scan(
        {
            "FRESH": _uptrend("2026-08-04"),
            "ALSOFRESH": _uptrend("2026-08-04"),
            "SUSPENDED": _downtrend("2026-07-20"),
        }
    ).drop_stale()
    assert sorted(r.symbol for r in result.readings) == ["ALSOFRESH", "FRESH"]
    assert "SUSPENDED" in result.skipped
    assert result.stale == []


def test_no_warning_when_data_is_from_today():
    result = scan({"AAA": _uptrend("2026-08-04")})
    assert report.freshness_warning(result, today=date(2026, 8, 4)) is None


def test_warning_when_data_lags_today():
    result = scan({"AAA": _uptrend("2026-08-04")})
    warning = report.freshness_warning(result, today=date(2026, 8, 6))
    assert warning is not None
    assert "2026-08-04" in warning and "2 days behind" in warning


def test_warning_uses_singular_for_one_day():
    result = scan({"AAA": _uptrend("2026-08-04")})
    warning = report.freshness_warning(result, today=date(2026, 8, 5))
    assert "1 day behind" in warning


def test_no_warning_when_clock_is_behind_the_data():
    # Running from a machine whose date lags the exchange is not staleness.
    result = scan({"AAA": _uptrend("2026-08-04")})
    assert report.freshness_warning(result, today=date(2026, 8, 3)) is None


def test_as_of_line_names_the_session():
    result = scan({"AAA": _uptrend("2026-08-04")})
    assert "2026-08-04" in report.as_of_line(result)


def test_as_of_line_without_data():
    assert "No stocks" in report.as_of_line(ScanResult())


def test_summary_reports_lagging_count():
    result = scan(
        {
            "FRESH": _uptrend("2026-08-04"),
            "ALSOFRESH": _uptrend("2026-08-04"),
            "SUSPENDED": _downtrend("2026-07-20"),
        }
    )
    assert "lagging the session: 1" in report.summary_line(result, 3, "file")
    assert "lagging" not in report.summary_line(result.drop_stale(), 3, "file")


def test_output_path_placeholder_expands_to_session_date():
    result = scan({"AAA": _uptrend("2026-08-04")})
    path = report.resolve_output_path("scans/ichimoku-{date}.csv", result)
    assert path.name == "ichimoku-2026-08-04.csv"


def test_output_path_without_placeholder_is_untouched():
    result = scan({"AAA": _uptrend("2026-08-04")})
    assert str(report.resolve_output_path("out.csv", result)) == "out.csv"


def test_output_path_falls_back_to_today_without_readings():
    path = report.resolve_output_path("out-{date}.csv", ScanResult())
    assert ist_today().isoformat() in path.name


def test_ist_today_is_a_date():
    assert isinstance(ist_today(), date)
