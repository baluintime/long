import numpy as np
import pandas as pd

from renko_screener import cli, universe
from renko_screener.report import COLUMNS, render_console, rows_to_frame
from renko_screener.signals import ScreenerRow, Signal


def _row(symbol: str, signal: Signal, bull_age=None, kijun=None) -> ScreenerRow:
    return ScreenerRow(symbol, 12.5, 0.12, 61.3, signal, bull_age, kijun)


def test_rows_to_frame_orders_actionable_first():
    rows = [
        _row("ZZZ", Signal.NO_TRADE),
        _row("BBB", Signal.ENTER_LONG, bull_age=2, kijun=100.0),
        _row("AAA", Signal.HOLD_RSI_EXHAUSTION, bull_age=5, kijun=90.0),
        _row("CCC", Signal.HOLD_LOW_VOLUME, bull_age=1, kijun=80.0),
    ]
    frame = rows_to_frame(rows)
    assert list(frame.columns) == COLUMNS
    assert list(frame["Symbol"]) == ["BBB", "AAA", "CCC", "ZZZ"]


def test_render_console_only_actionable():
    frame = rows_to_frame(
        [
            _row("AAA", Signal.ENTER_LONG, bull_age=1, kijun=100.0),
            _row("BBB", Signal.NO_TRADE),
        ]
    )
    text = render_console(frame, only_actionable=True)
    assert "AAA" in text and "BBB" not in text


def test_load_universe(tmp_path):
    path = tmp_path / "universe.txt"
    path.write_text("# comment\nreliance\nTCS\n\nTCS # duplicate\n")
    assert universe.load_universe(path) == ["RELIANCE", "TCS"]


def test_default_universe_loads():
    symbols = universe.load_universe()
    assert len(symbols) > 150
    assert "RELIANCE" in symbols and "TCS" in symbols


def test_cli_scan_from_csv(tmp_path, capsys):
    # End-to-end: an uptrending symbol from CSV produces an ENTER LONG row.
    moves = np.tile([2.0, -1.0], 450)
    closes = 100.0 + np.cumsum(moves)
    opens = np.concatenate([[closes[0]], closes[:-1]])
    frame = pd.DataFrame(
        {
            "Date": pd.bdate_range("2022-01-03", periods=len(closes)),
            "Open": opens,
            "High": np.maximum(opens, closes) + 0.5,
            "Low": np.minimum(opens, closes) - 0.5,
            "Close": closes,
            "Volume": np.full(len(closes), 1_000_000.0),
        }
    )
    frame.to_csv(tmp_path / "UPTREND.csv", index=False)

    out_csv = tmp_path / "report.csv"
    exit_code = cli.main(
        [
            "scan",
            "--symbols",
            "UPTREND",
            "--source",
            "csv",
            "--csv-dir",
            str(tmp_path),
            "--output",
            str(out_csv),
        ]
    )
    assert exit_code == 0
    printed = capsys.readouterr().out
    assert "UPTREND" in printed and "ENTER LONG" in printed

    written = pd.read_csv(out_csv)
    assert list(written.columns) == COLUMNS
    assert written.loc[0, "Signal Trigger"] == "ENTER LONG"


def test_cli_csv_source_requires_dir(capsys):
    assert cli.main(["scan", "--symbols", "X", "--source", "csv"]) == 2
