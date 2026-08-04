"""Output: the stock names in each Ichimoku position, plus optional detail."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pandas as pd

from .ichimoku import IchimokuReading, Position
from .screener import ScanResult, ist_today

#: Every field, in the order they appear in the spreadsheet.
DETAIL_COLUMNS = [
    "Symbol",
    "Date",
    "Close",
    "Position",
    "Tenkan",
    "Kijun",
    "Senkou A",
    "Senkou B",
    "Cloud Top",
    "Cloud Bottom",
    "% vs Tenkan",
    "% vs Kijun",
    "% vs Senkou A",
    "% vs Senkou B",
    "% vs Cloud Top",
    "% vs Cloud Bottom",
    "% to Nearest Line",
    "Chikou Clear",
]

#: Percentage columns, for number formatting and console selection.
PERCENT_COLUMNS = [c for c in DETAIL_COLUMNS if c.startswith("%")]

#: Price columns, kept apart because they format differently.
PRICE_COLUMNS = ["Close", "Tenkan", "Kijun", "Senkou A", "Senkou B", "Cloud Top", "Cloud Bottom"]

#: A terminal-friendly subset: the percentages are the point of the table.
CONSOLE_COLUMNS = [
    "Symbol",
    "Date",
    "Close",
    "Position",
    "% vs Tenkan",
    "% vs Kijun",
    "% vs Senkou A",
    "% vs Senkou B",
    "% to Nearest Line",
]


def _wrap_names(names: list[str], width: int | None = None) -> str:
    """Lay symbols out in columns that fit the terminal."""
    if not names:
        return "  (none)"
    if width is None:
        width = shutil.get_terminal_size((100, 24)).columns
    column_width = max(len(n) for n in names) + 2
    per_row = max(1, (width - 2) // column_width)
    lines = []
    for start in range(0, len(names), per_row):
        row = names[start : start + per_row]
        lines.append("  " + "".join(name.ljust(column_width) for name in row).rstrip())
    return "\n".join(lines)


def as_of_line(result: ScanResult) -> str:
    """Name the trading session these results describe."""
    as_of = result.as_of
    if as_of is None:
        return "No stocks had enough history to place against the cloud."
    return f"Ichimoku positions as of {as_of.date().isoformat()} (latest NSE daily close)"


def freshness_warning(result: ScanResult, today: date | None = None) -> str | None:
    """Flag a scan whose newest bar is not today's session.

    A once-a-day post-close run should be looking at today's close. If it
    is not — a market holiday, a weekend, or a feed that has not published
    yet — say so rather than let yesterday's data pass for current.
    """
    as_of = result.as_of
    if as_of is None:
        return None
    today = today or ist_today()
    lag = (today - as_of.date()).days
    if lag <= 0:
        return None
    day_word = "day" if lag == 1 else "days"
    return (
        f"warning: the latest daily bar is {as_of.date().isoformat()}, "
        f"{lag} {day_word} behind today ({today.isoformat()} IST). "
        "Market holiday or weekend, or the price feed has not published "
        "today's close yet — re-run later if you expected today's session."
    )


def _count(names: list[str]) -> str:
    return f"{len(names)} stock" if len(names) == 1 else f"{len(names)} stocks"


def render_names(result: ScanResult, show_mixed: bool = False) -> str:
    """The headline output: which stocks sit above / below all Ichimoku lines."""
    above = [r.symbol for r in result.above]
    below = [r.symbol for r in result.below]

    sections = [
        f"ABOVE ALL ICHIMOKU LINES — bullish ({_count(above)})",
        _wrap_names(above),
        "",
        f"BELOW ALL ICHIMOKU LINES — bearish ({_count(below)})",
        _wrap_names(below),
    ]
    if show_mixed:
        mixed = [r.symbol for r in result.mixed]
        sections += [
            "",
            f"MIXED — close tangled in the lines ({_count(mixed)})",
            _wrap_names(mixed),
        ]
    return "\n".join(sections)


def _row(reading: IchimokuReading) -> dict[str, object]:
    gaps = reading.percent_gaps
    return {
        "Symbol": reading.symbol,
        "Date": reading.date.date().isoformat(),
        "Close": round(reading.close, 2),
        "Position": str(reading.position),
        "Tenkan": round(reading.tenkan, 2),
        "Kijun": round(reading.kijun, 2),
        "Senkou A": round(reading.senkou_a, 2),
        "Senkou B": round(reading.senkou_b, 2),
        "Cloud Top": round(reading.cloud_top, 2),
        "Cloud Bottom": round(reading.cloud_bottom, 2),
        "% vs Tenkan": round(gaps["tenkan"], 2),
        "% vs Kijun": round(gaps["kijun"], 2),
        "% vs Senkou A": round(gaps["senkou_a"], 2),
        "% vs Senkou B": round(gaps["senkou_b"], 2),
        "% vs Cloud Top": round(gaps["cloud_top"], 2),
        "% vs Cloud Bottom": round(gaps["cloud_bottom"], 2),
        "% to Nearest Line": round(reading.percent_to_nearest_line, 2),
        "Chikou Clear": reading.chikou_clear,
    }


def readings_to_frame(readings: list[IchimokuReading]) -> pd.DataFrame:
    return pd.DataFrame([_row(r) for r in readings], columns=DETAIL_COLUMNS)


def render_detail(result: ScanResult, show_mixed: bool = False) -> str:
    """Console table of percentage gaps; the raw levels live in the workbook."""
    from tabulate import tabulate

    readings = result.above + result.below
    if show_mixed:
        readings += result.mixed
    if not readings:
        return "No stocks with enough history to place against the cloud."
    frame = readings_to_frame(readings)[CONSOLE_COLUMNS]
    return tabulate(frame, headers="keys", tablefmt="github", showindex=False)


def all_readings(result: ScanResult) -> list[IchimokuReading]:
    """Every classified stock — exported files hold the complete scan."""
    return result.above + result.below + result.mixed


def write_csv(result: ScanResult, path: str | Path) -> None:
    readings_to_frame(all_readings(result)).to_csv(path, index=False)


def write_results(
    result: ScanResult, path: str | Path, universe_size: int, source: str
) -> Path:
    """Write the scan to ``path``, choosing the format from its extension."""
    out_path = Path(path)
    if out_path.suffix.lower() in (".xlsx", ".xlsm"):
        from .excel import write_workbook

        return write_workbook(result, out_path, universe_size, source)
    write_csv(result, out_path)
    return out_path


def summary_line(result: ScanResult, universe_size: int, source: str) -> str:
    counts = {p: len(result.by_position(p)) for p in Position}
    parts = [
        f"Universe: {universe_size} NSE symbols (source: {source})",
        f"evaluated: {len(result.readings)}",
        f"above: {counts[Position.ABOVE]}",
        f"below: {counts[Position.BELOW]}",
        f"mixed: {counts[Position.MIXED]}",
        f"skipped (no/short data): {len(result.skipped)}",
    ]
    stale = result.stale
    if stale:
        parts.append(f"lagging the session: {len(stale)}")
    return " | ".join(parts)


def resolve_output_path(path: str | Path, result: ScanResult) -> Path:
    """Expand a ``{date}`` placeholder so daily runs do not overwrite each other."""
    as_of = result.as_of
    stamp = (as_of.date() if as_of is not None else ist_today()).isoformat()
    return Path(str(path).replace("{date}", stamp))
