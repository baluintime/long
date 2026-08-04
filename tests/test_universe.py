import pandas as pd
import pytest

from nse_ichimoku import universe


def test_parse_equity_csv_filters_series():
    text = (
        "SYMBOL,NAME OF COMPANY,SERIES\n"
        "RELIANCE,Reliance Industries,EQ\n"
        "TCS,Tata Consultancy,EQ\n"
        "SOMEBOND,A Debt Instrument,N1\n"
        "TFTSTOCK,Trade For Trade,BE\n"
    )
    symbols = universe._parse_equity_csv(text, ("EQ", "BE"))
    assert symbols == ["RELIANCE", "TCS", "TFTSTOCK"]
    assert "SOMEBOND" not in symbols


def test_parse_equity_csv_deduplicates_and_uppercases():
    text = "SYMBOL,SERIES\nreliance,EQ\nRELIANCE,EQ\n tcs ,EQ\n"
    assert universe._parse_equity_csv(text, ("EQ",)) == ["RELIANCE", "TCS"]


def test_parse_equity_csv_without_series_column():
    text = "SYMBOL\nINFY\nWIPRO\n"
    assert universe._parse_equity_csv(text, ("EQ",)) == ["INFY", "WIPRO"]


def test_parse_equity_csv_requires_symbol_column():
    with pytest.raises(ValueError):
        universe._parse_equity_csv("NAME,SERIES\nfoo,EQ\n", ("EQ",))


def test_bundled_fallback_is_parseable():
    symbols = universe._parse_equity_csv(
        universe.BUNDLED_FALLBACK.read_text(), universe.DEFAULT_SERIES
    )
    assert len(symbols) > 150
    assert "RELIANCE" in symbols and "TCS" in symbols


def test_load_universe_from_text_file(tmp_path):
    path = tmp_path / "symbols.txt"
    path.write_text("# my list\nreliance\nTCS\n\nTCS  # duplicate\n")
    loaded = universe.load_universe(path)
    assert loaded.symbols == ["RELIANCE", "TCS"]
    assert loaded.source == "file"


def test_load_universe_from_csv_file(tmp_path):
    path = tmp_path / "equity.csv"
    path.write_text("SYMBOL,SERIES\nINFY,EQ\nBOND1,N2\n")
    loaded = universe.load_universe(path)
    assert loaded.symbols == ["INFY"]
    assert loaded.source == "file"


def test_load_universe_falls_back_when_nse_unreachable(monkeypatch, tmp_path):
    monkeypatch.setattr(universe, "CACHE_FILE", tmp_path / "missing.csv")
    monkeypatch.setattr(
        universe,
        "_download_equity_csv",
        lambda *a, **k: (_ for _ in ()).throw(ConnectionError("blocked")),
    )
    loaded = universe.load_universe()
    assert loaded.source == "bundled"
    assert "RELIANCE" in loaded.symbols


def test_load_universe_raises_when_fallback_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(universe, "CACHE_FILE", tmp_path / "missing.csv")
    monkeypatch.setattr(
        universe,
        "_download_equity_csv",
        lambda *a, **k: (_ for _ in ()).throw(ConnectionError("blocked")),
    )
    with pytest.raises(ConnectionError):
        universe.load_universe(allow_fallback=False)


def test_load_universe_uses_and_writes_cache(monkeypatch, tmp_path):
    cache = tmp_path / "cache.csv"
    monkeypatch.setattr(universe, "CACHE_FILE", cache)
    monkeypatch.setattr(universe, "DATA_DIR", tmp_path)
    calls = []

    def fake_download(*args, **kwargs):
        calls.append(1)
        return "SYMBOL,SERIES\nHDFCBANK,EQ\nSBIN,EQ\n"

    monkeypatch.setattr(universe, "_download_equity_csv", fake_download)

    first = universe.load_universe()
    assert first.source == "nse" and first.symbols == ["HDFCBANK", "SBIN"]
    assert cache.exists()

    second = universe.load_universe()
    assert second.source == "cache" and second.symbols == ["HDFCBANK", "SBIN"]
    assert len(calls) == 1  # served from cache, no second download

    third = universe.load_universe(refresh=True)
    assert third.source == "nse"
    assert len(calls) == 2


def test_load_universe_ignores_stale_cache(monkeypatch, tmp_path):
    cache = tmp_path / "cache.csv"
    cache.write_text("SYMBOL,SERIES\nOLDSYM,EQ\n")
    monkeypatch.setattr(universe, "CACHE_FILE", cache)
    monkeypatch.setattr(universe, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        universe, "_download_equity_csv", lambda *a, **k: "SYMBOL,SERIES\nNEWSYM,EQ\n"
    )
    loaded = universe.load_universe(cache_max_age=-1)
    assert loaded.symbols == ["NEWSYM"]
