"""Output: the stock names in each Ichimoku position, plus optional detail."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pandas as pd

from .ichimoku import IchimokuReading, Position
from .screener import ScanResult, ist_today

DETAIL_COLUMNS = [
    "Symbol",
    "Date",
    "Close",
    "Tenkan",
    "Kijun",
    "Senkou A",
    "Senkou B",
    "Position",
    "Chikou Clear",
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


def readings_to_frame(readings: list[IchimokuReading]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Symbol": r.symbol,
                "Date": r.date.date().isoformat(),
                "Close": round(r.close, 2),
                "Tenkan": round(r.tenkan, 2),
                "Kijun": round(r.kijun, 2),
                "Senkou A": round(r.senkou_a, 2),
                "Senkou B": round(r.senkou_b, 2),
                "Position": str(r.position),
                "Chikou Clear": r.chikou_clear,
            }
            for r in readings
        ],
        columns=DETAIL_COLUMNS,
    )


def render_detail(result: ScanResult, show_mixed: bool = False) -> str:
    from tabulate import tabulate

    readings = result.above + result.below
    if show_mixed:
        readings += result.mixed
    if not readings:
        return "No stocks with enough history to place against the cloud."
    frame = readings_to_frame(readings)
    return tabulate(frame, headers="keys", tablefmt="github", showindex=False)


def write_csv(result: ScanResult, path: str | Path, show_mixed: bool = False) -> None:
    readings = result.above + result.below
    if show_mixed:
        readings += result.mixed
    readings_to_frame(readings).to_csv(path, index=False)


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
