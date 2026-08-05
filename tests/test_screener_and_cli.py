import numpy as np
import pandas as pd
import pytest

from nse_ichimoku import cli, report
from nse_ichimoku.ichimoku import Position
from nse_ichimoku.screener import scan


def _ohlc(closes) -> pd.DataFrame:
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes + 0.5,
            "Low": closes - 0.5,
            "Close": closes,
        },
        index=pd.bdate_range("2024-01-01", periods=len(closes)),
    )


UPTREND = _ohlc(np.arange(100, 300, dtype=float))
DOWNTREND = _ohlc(np.arange(300, 100, -1, dtype=float))
FLAT = _ohlc(100 + 0.5 * np.sin(np.linspace(0, 12, 200)))
SHORT = _ohlc(np.arange(100, 140, dtype=float))


@pytest.fixture
def price_data():
    return {
        "BULLCO": UPTREND,
        "BEARCO": DOWNTREND,
        "FLATCO": FLAT,
        "NEWLIST": SHORT,
    }


def test_scan_groups_by_position(price_data):
    result = scan(price_data)
    assert [r.symbol for r in result.above] == ["BULLCO"]
    assert [r.symbol for r in result.below] == ["BEARCO"]
    assert [r.symbol for r in result.mixed] == ["FLATCO"]
    # Not enough history for a full cloud, and the reason says so.
    assert list(result.skipped) == ["NEWLIST"]
    assert "insufficient history" in result.skipped["NEWLIST"]


def test_scan_skips_unusable_frames():
    result = scan({"BROKEN": pd.DataFrame({"Close": [1.0, 2.0]})})
    assert result.readings == []
    assert result.skipped["BROKEN"] == "missing columns: High, Low"


def test_render_names_lists_both_sides(price_data):
    text = report.render_names(scan(price_data))
    assert "ABOVE ALL ICHIMOKU LINES" in text and "BULLCO" in text
    assert "BELOW ALL ICHIMOKU LINES" in text and "BEARCO" in text
    assert "FLATCO" not in text  # mixed is hidden unless asked for


def test_render_names_can_show_mixed(price_data):
    text = report.render_names(scan(price_data), show_mixed=True)
    assert "FLATCO" in text


def test_render_names_handles_empty_side():
    text = report.render_names(scan({"BULLCO": UPTREND}))
    assert "(none)" in text


def test_readings_to_frame_columns(price_data):
    frame = report.readings_to_frame(scan(price_data).above)
    assert list(frame.columns) == report.DETAIL_COLUMNS
    assert frame.loc[0, "Symbol"] == "BULLCO"
    assert frame.loc[0, "Position"] == "ABOVE"


def _write_csvs(directory, frames: dict[str, pd.DataFrame]) -> None:
    for symbol, frame in frames.items():
        out = frame.copy()
        out.index.name = "Date"
        out.to_csv(directory / f"{symbol}.csv")


def test_cli_end_to_end_from_csv(tmp_path, capsys):
    _write_csvs(tmp_path, {"BULLCO": UPTREND, "BEARCO": DOWNTREND, "FLATCO": FLAT})
    out_csv = tmp_path / "out.csv"

    exit_code = cli.main(
        [
            "--symbols",
            "BULLCO",
            "BEARCO",
            "FLATCO",
            "MISSING",
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
    assert "BULLCO" in printed and "BEARCO" in printed
    assert "above: 1" in printed and "below: 1" in printed
    assert "skipped (no/short data): 1" in printed  # MISSING had no file

    # Exported files carry the whole scan, including the mixed stocks the
    # console hides.
    written = pd.read_csv(out_csv)
    assert set(written["Symbol"]) == {"BULLCO", "BEARCO", "FLATCO"}
    assert set(written["Position"]) == {"ABOVE", "BELOW", "MIXED"}


def test_cli_detail_mode(tmp_path, capsys):
    _write_csvs(tmp_path, {"BULLCO": UPTREND})
    assert (
        cli.main(
            [
                "--symbols",
                "BULLCO",
                "--source",
                "csv",
                "--csv-dir",
                str(tmp_path),
                "--detail",
                "--no-file",
            ]
        )
        == 0
    )
    printed = capsys.readouterr().out
    assert "Tenkan" in printed and "Senkou B" in printed and "BULLCO" in printed


def test_cli_limit_applies_to_universe(tmp_path, capsys, monkeypatch):
    _write_csvs(tmp_path, {"BULLCO": UPTREND, "BEARCO": DOWNTREND})
    universe_file = tmp_path / "universe.txt"
    universe_file.write_text("BULLCO\nBEARCO\n")

    assert (
        cli.main(
            [
                "--universe-file",
                str(universe_file),
                "--limit",
                "1",
                "--source",
                "csv",
                "--csv-dir",
                str(tmp_path),
                "--no-file",
            ]
        )
        == 0
    )
    printed = capsys.readouterr().out
    assert "Universe: 1 NSE symbols" in printed


def test_cli_csv_source_requires_dir(capsys):
    assert cli.main(["--symbols", "X", "--source", "csv"]) == 2
    assert "--csv-dir is required" in capsys.readouterr().err
