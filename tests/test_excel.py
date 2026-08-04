"""The Excel workbook is the complete record of a scan."""

import numpy as np
import pandas as pd
import pytest

from nse_ichimoku import cli, report
from nse_ichimoku.excel import build_sheets, build_summary, write_workbook
from nse_ichimoku.screener import scan

openpyxl = pytest.importorskip("openpyxl")


def _ohlc(closes) -> pd.DataFrame:
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {"Open": closes, "High": closes + 0.5, "Low": closes - 0.5, "Close": closes},
        index=pd.bdate_range(end="2026-08-04", periods=len(closes)),
    )


UPTREND = _ohlc(np.arange(100, 300, dtype=float))
STEEPER = _ohlc(np.arange(100, 500, 2.0))
DOWNTREND = _ohlc(np.arange(300, 100, -1, dtype=float))
FLAT = _ohlc(100 + 0.5 * np.sin(np.linspace(0, 12, 200)))


@pytest.fixture
def result():
    return scan(
        {"BULLCO": UPTREND, "ROCKET": STEEPER, "BEARCO": DOWNTREND, "FLATCO": FLAT}
    )


def test_sheets_cover_every_position(result):
    sheets = build_sheets(result)
    assert set(sheets) == {"Above", "Below", "Mixed", "All"}
    assert set(sheets["All"]["Symbol"]) == {"BULLCO", "ROCKET", "BEARCO", "FLATCO"}
    assert set(sheets["Above"]["Position"]) == {"ABOVE"}
    assert set(sheets["Below"]["Position"]) == {"BELOW"}
    assert set(sheets["Mixed"]["Symbol"]) == {"FLATCO"}


def test_above_sheet_leads_with_the_widest_cushion(result):
    above = build_sheets(result)["Above"]
    gaps = list(above["% to Nearest Line"])
    assert gaps == sorted(gaps, reverse=True)


def test_below_sheet_leads_with_the_deepest_position(result):
    below = build_sheets(result)["Below"]
    gaps = list(below["% to Nearest Line"])
    assert gaps == sorted(gaps)


def test_summary_reports_the_session_and_counts(result):
    summary = build_summary(result, universe_size=4, source="file")
    values = dict(zip(summary["Metric"], summary["Value"]))
    assert values["Session (as of)"] == "2026-08-04"
    assert values["Universe size"] == 4
    assert values["Universe source"] == "file"
    assert values["Above all Ichimoku lines"] == 2
    assert values["Below all Ichimoku lines"] == 1
    assert values["Mixed"] == 1


def test_workbook_round_trips(tmp_path, result):
    path = write_workbook(result, tmp_path / "out.xlsx", 4, "file")
    assert path.exists()

    book = openpyxl.load_workbook(path)
    assert book.sheetnames == ["Summary", "Above", "Below", "Mixed", "All"]

    sheet = book["All"]
    headers = [cell.value for cell in sheet[1]]
    assert headers == report.DETAIL_COLUMNS

    frame = pd.read_excel(path, sheet_name="All")
    assert len(frame) == 4
    bull = frame[frame["Symbol"] == "BULLCO"].iloc[0]
    expected = (bull["Close"] - bull["Kijun"]) / bull["Kijun"] * 100
    assert bull["% vs Kijun"] == pytest.approx(expected, abs=0.01)


def test_workbook_is_formatted_for_reading(tmp_path, result):
    path = write_workbook(result, tmp_path / "out.xlsx", 4, "file")
    sheet = openpyxl.load_workbook(path)["All"]

    assert sheet.freeze_panes == "B2"  # symbol column stays visible
    assert sheet.auto_filter.ref is not None
    assert sheet[1][0].font.bold

    percent_index = report.DETAIL_COLUMNS.index("% vs Tenkan") + 1
    assert '0.00"%"' in sheet.cell(row=2, column=percent_index).number_format


def test_empty_sheets_still_carry_headers(tmp_path):
    only_bull = scan({"BULLCO": UPTREND})
    path = write_workbook(only_bull, tmp_path / "out.xlsx", 1, "file")
    sheet = openpyxl.load_workbook(path)["Below"]
    assert [cell.value for cell in sheet[1]] == report.DETAIL_COLUMNS
    assert sheet.max_row == 1


def test_workbook_creates_missing_directories(tmp_path, result):
    path = write_workbook(result, tmp_path / "scans" / "2026" / "out.xlsx", 4, "file")
    assert path.exists()


def _write_csvs(directory, frames):
    for symbol, frame in frames.items():
        out = frame.copy()
        out.index.name = "Date"
        out.to_csv(directory / f"{symbol}.csv")


def test_cli_writes_excel_from_extension(tmp_path, capsys):
    _write_csvs(tmp_path, {"BULLCO": UPTREND, "BEARCO": DOWNTREND, "FLATCO": FLAT})
    out = tmp_path / "scan-{date}.xlsx"

    assert (
        cli.main(
            [
                "--symbols",
                "BULLCO",
                "BEARCO",
                "FLATCO",
                "--source",
                "csv",
                "--csv-dir",
                str(tmp_path),
                "--output",
                str(out),
            ]
        )
        == 0
    )
    written = tmp_path / "scan-2026-08-04.xlsx"
    assert written.exists()
    assert str(written) in capsys.readouterr().out

    frame = pd.read_excel(written, sheet_name="All")
    assert set(frame["Symbol"]) == {"BULLCO", "BEARCO", "FLATCO"}
    assert "% to Nearest Line" in frame.columns


def test_cli_output_flag_defaults_to_a_dated_workbook(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_csvs(tmp_path, {"BULLCO": UPTREND})
    assert (
        cli.main(
            ["--symbols", "BULLCO", "--source", "csv", "--csv-dir", str(tmp_path), "--output"]
        )
        == 0
    )
    assert (tmp_path / "ichimoku-2026-08-04.xlsx").exists()
