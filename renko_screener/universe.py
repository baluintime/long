"""NSE F&O universe loading.

The default universe lives in ``data/fo_universe.txt`` at the repository
root — one NSE symbol per line, ``#`` starts a comment. Edit that file when
NSE adds or removes derivative contracts.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_UNIVERSE_FILE = Path(__file__).resolve().parent.parent / "data" / "fo_universe.txt"


def load_universe(path: str | Path | None = None) -> list[str]:
    file_path = Path(path) if path else DEFAULT_UNIVERSE_FILE
    symbols: list[str] = []
    seen: set[str] = set()
    for raw in file_path.read_text().splitlines():
        symbol = raw.split("#", 1)[0].strip().upper()
        if symbol and symbol not in seen:
            seen.add(symbol)
            symbols.append(symbol)
    return symbols
