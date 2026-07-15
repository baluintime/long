"""EOD report rendering: console table and CSV export (PRD v2.0, section 4)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .signals import ScreenerRow, Signal

COLUMNS = [
    "Symbol",
    "Brick Size (ATR 14)",
    "CMF Value (21)",
    "RSI (14)",
    "Signal Trigger",
    "Bull-Age (Days)",
    "Kijun-sen Level",
]

# Actionable rows first, then holds, then no-trades; alphabetical within group.
_SIGNAL_ORDER = {
    Signal.ENTER_LONG: 0,
    Signal.HOLD_RSI_EXHAUSTION: 1,
    Signal.HOLD_LOW_VOLUME: 2,
    Signal.NO_TRADE: 3,
}


def rows_to_frame(rows: list[ScreenerRow]) -> pd.DataFrame:
    ordered = sorted(rows, key=lambda r: (_SIGNAL_ORDER[r.signal], r.symbol))
    frame = pd.DataFrame(
        [
            {
                "Symbol": r.symbol,
                "Brick Size (ATR 14)": round(r.brick_size, 2),
                "CMF Value (21)": round(r.cmf_value, 3),
                "RSI (14)": round(r.rsi_value, 1),
                "Signal Trigger": str(r.signal),
                "Bull-Age (Days)": r.bull_age_days,
                "Kijun-sen Level": round(r.kijun_level, 2) if r.kijun_level is not None else None,
            }
            for r in ordered
        ],
        columns=COLUMNS,
    )
    frame["Bull-Age (Days)"] = frame["Bull-Age (Days)"].astype("Int64")
    return frame


def render_console(frame: pd.DataFrame, only_actionable: bool = False) -> str:
    from tabulate import tabulate

    if only_actionable:
        frame = frame[frame["Signal Trigger"] == Signal.ENTER_LONG.value]
    if frame.empty:
        return "No rows to display."
    display = frame.astype(object).where(frame.notna(), "-")
    return tabulate(display, headers="keys", tablefmt="github", showindex=False)


def write_csv(frame: pd.DataFrame, path: str | Path) -> None:
    frame.to_csv(path, index=False)
