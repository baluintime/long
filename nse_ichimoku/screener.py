"""Run the Ichimoku position check across a set of symbols."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from .ichimoku import IchimokuReading, Position, read_latest

log = logging.getLogger(__name__)


@dataclass
class ScanResult:
    readings: list[IchimokuReading] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # no data / too little history

    def by_position(self, position: Position) -> list[IchimokuReading]:
        return sorted(
            (r for r in self.readings if r.position is position),
            key=lambda r: r.symbol,
        )

    @property
    def above(self) -> list[IchimokuReading]:
        return self.by_position(Position.ABOVE)

    @property
    def below(self) -> list[IchimokuReading]:
        return self.by_position(Position.BELOW)

    @property
    def mixed(self) -> list[IchimokuReading]:
        return self.by_position(Position.MIXED)


def scan(price_data: dict[str, pd.DataFrame]) -> ScanResult:
    """Classify every symbol whose data supports a complete Ichimoku read."""
    result = ScanResult()
    for symbol in sorted(price_data):
        try:
            reading = read_latest(symbol, price_data[symbol])
        except Exception as exc:
            log.warning("failed to evaluate %s: %s", symbol, exc)
            result.skipped.append(symbol)
            continue
        if reading is None:
            result.skipped.append(symbol)
        else:
            result.readings.append(reading)
    return result
