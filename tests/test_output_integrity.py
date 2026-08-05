"""The written file must be one Excel will actually open.

Excel reports "the file format or file extension is not valid" whenever an
.xlsx turns out to be CSV text or a truncated file, so these tests pin the
guarantees that prevent it.
"""

import numpy as np
import pandas as pd
import pytest

from nse_ichimoku import cli, report
from nse_ichimoku.excel import ZIP_MAGIC, verify_workbook, write_workbook
from nse_ichimoku.screener import scan

openpyxl = pytest.importorskip("openpyxl")


def _ohlc(closes) -> pd.DataFrame:
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {"Open": closes, "High": closes + 0.5, "Low": closes - 0.5, "Close": closes},
        index=pd.bdate_range(end="2026-08-05", periods=len(closes)),
    )


UPTREND = _ohlc(np.arange(100, 300, dtype=float))
DOWNTREND = _ohlc(np.arange(300, 100, -1, dtype=float))


@pytest.fixture
def result():
    return scan({"BULLCO": UPTREND, "BEARCO": DOWNTREND})


def test_workbook_is_a_real_zip_archive(tmp_path, result):
    path = write_workbook(result, tmp_path / "out.xlsx", 2, "file")
    with open(path, "rb") as handle:
        assert handle.read(2) == ZIP_MAGIC


def test_workbook_opens_as_excel_and_not_as_text(tmp_path, result):
    path = write_workbook(result, tmp_path / "out.xlsx", 2, "file")
    # The failure mode being guarded against: a CSV header at byte zero.
    with open(path, "rb") as handle:
        assert not handle.read(16).startswith(b"Symbol")
    assert openpyxl.load_workbook(path).sheetnames[0] == "Summary"


def test_verify_rejects_csv_text_named_xlsx(tmp_path):
    impostor = tmp_path / "fake.xlsx"
    impostor.write_text("Symbol,Date,Close\nRELIANCE,2026-08-05,1400\n")
    with pytest.raises(ValueError, match="not a valid .xlsx"):
        verify_workbook(impostor)


def test_verify_rejects_an_empty_file(tmp_path):
    empty = tmp_path / "empty.xlsx"
    empty.touch()
    with pytest.raises(ValueError, match="empty"):
        verify_workbook(empty)


def test_verify_rejects_a_truncated_workbook(tmp_path, result):
    path = write_workbook(result, tmp_path / "out.xlsx", 2, "file")
    data = path.read_bytes()
    path.write_bytes(data[: len(data) // 2])  # interrupted mid-write
    with pytest.raises(Exception):
        verify_workbook(path)


def test_verify_rejects_a_missing_file(tmp_path):
    with pytest.raises(ValueError, match="was not created"):
        verify_workbook(tmp_path / "nope.xlsx")


def test_a_failed_write_leaves_no_file_behind(tmp_path, result, monkeypatch):
    import nse_ichimoku.excel as excel

    monkeypatch.setattr(
        excel,
        "_write_sheets",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk full")),
    )
    target = tmp_path / "out.xlsx"
    with pytest.raises(RuntimeError):
        write_workbook(result, target, 2, "file")

    assert not target.exists()
    assert list(tmp_path.iterdir()) == []  # no temp file left over either


def test_a_failed_write_preserves_the_previous_workbook(tmp_path, result, monkeypatch):
    import nse_ichimoku.excel as excel

    target = write_workbook(result, tmp_path / "out.xlsx", 2, "file")
    original = target.read_bytes()

    monkeypatch.setattr(
        excel,
        "_write_sheets",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("crash")),
    )
    with pytest.raises(RuntimeError):
        write_workbook(result, target, 2, "file")

    assert target.read_bytes() == original


def test_formatting_failure_still_yields_a_valid_workbook(tmp_path, result, monkeypatch):
    import nse_ichimoku.excel as excel

    monkeypatch.setattr(
        excel,
        "_style_sheet",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bad style")),
    )
    path = write_workbook(result, tmp_path / "out.xlsx", 2, "file")
    verify_workbook(path)
    frame = pd.read_excel(path, sheet_name="All")
    assert set(frame["Symbol"]) == {"BULLCO", "BEARCO"}


def test_write_results_reports_the_format_it_wrote(tmp_path, result):
    _, kind = report.write_results(result, tmp_path / "a.xlsx", 2, "file")
    assert kind == "Excel workbook"
    _, kind = report.write_results(result, tmp_path / "a.csv", 2, "file")
    assert kind == "CSV"


def test_excel_extension_never_receives_csv_text(tmp_path, result, monkeypatch):
    """Without openpyxl the run fails loudly instead of writing CSV as .xlsx."""
    import builtins

    real_import = builtins.__import__

    def no_openpyxl(name, *args, **kwargs):
        if name.startswith("openpyxl"):
            raise ImportError("No module named 'openpyxl'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_openpyxl)
    with pytest.raises(ImportError):
        report.write_results(result, tmp_path / "out.xlsx", 2, "file")
    assert not (tmp_path / "out.xlsx").exists()


def _write_csvs(directory, frames):
    for symbol, frame in frames.items():
        out = frame.copy()
        out.index.name = "Date"
        out.to_csv(directory / f"{symbol}.csv")


def test_cli_names_the_format_it_wrote(tmp_path, capsys):
    _write_csvs(tmp_path, {"BULLCO": UPTREND})
    out = tmp_path / "scan.xlsx"
    assert (
        cli.main(
            [
                "--symbols",
                "BULLCO",
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
    assert "Excel workbook written to" in capsys.readouterr().out
    verify_workbook(out)


def test_cli_reports_a_write_failure_without_crashing(tmp_path, capsys, monkeypatch):
    _write_csvs(tmp_path, {"BULLCO": UPTREND})
    import nse_ichimoku.excel as excel

    monkeypatch.setattr(
        excel,
        "_write_sheets",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk full")),
    )
    exit_code = cli.main(
        [
            "--symbols",
            "BULLCO",
            "--source",
            "csv",
            "--csv-dir",
            str(tmp_path),
            "--output",
            str(tmp_path / "scan.xlsx"),
        ]
    )
    assert exit_code == 1
    assert "could not write" in capsys.readouterr().err
