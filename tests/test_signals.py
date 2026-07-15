import numpy as np
import pandas as pd

from renko_screener.signals import Signal, evaluate_symbol


def _ohlcv(closes, high_offset=0.5, low_offset=0.5) -> pd.DataFrame:
    """Build a daily OHLCV frame from a close path.

    Each bar opens at the previous close; high/low are offsets beyond the
    bar's body so the close's position inside the range (and hence CMF) is
    controlled by the offsets.
    """
    closes = np.asarray(closes, dtype=float)
    opens = np.concatenate([[closes[0]], closes[:-1]])
    body_high = np.maximum(opens, closes)
    body_low = np.minimum(opens, closes)
    idx = pd.bdate_range("2022-01-03", periods=len(closes))
    return pd.DataFrame(
        {
            "Open": opens,
            "High": body_high + high_offset,
            "Low": body_low - low_offset,
            "Close": closes,
            "Volume": np.full(len(closes), 1_000_000.0),
        },
        index=idx,
    )


def _staircase_up(days: int, up: float = 2.0, down: float = 1.0, start: float = 100.0):
    """Alternating +up/-down close path: net uptrend with RSI well below 75."""
    moves = np.tile([up, -down], days // 2 + 1)[:days]
    return start + np.cumsum(moves)


def test_enter_long_on_confirmed_uptrend():
    # Net uptrend (bricks green, above cloud), closes near bar highs
    # (CMF > +0.05), alternating pullbacks keep RSI(14) ~ 67 < 75.
    frame = _ohlcv(_staircase_up(900))
    row = evaluate_symbol("TEST", frame)
    assert row.signal == Signal.ENTER_LONG
    assert row.cmf_value > 0.05
    assert row.rsi_value < 75
    assert row.brick_size > 0
    assert row.bull_age_days is not None and row.bull_age_days >= 0
    assert row.kijun_level is not None and row.kijun_level < frame["Close"].iloc[-1]


def test_hold_rsi_exhaustion_on_vertical_run():
    # Monotonic rise: trend and CMF pass, but RSI(14) = 100 >= 75.
    closes = 100.0 + np.cumsum(np.full(900, 1.0))
    frame = _ohlcv(closes, high_offset=0.25, low_offset=1.0)
    row = evaluate_symbol("TEST", frame)
    assert row.signal == Signal.HOLD_RSI_EXHAUSTION
    assert row.rsi_value >= 75
    assert row.cmf_value > 0.05


def test_hold_low_volume_when_cmf_weak():
    # Uptrend, but every close sits at the bottom of a wide bar: CMF < 0,
    # so the breakout is a "Low-Volume Trap".
    closes = 100.0 + np.cumsum(np.full(900, 2.0))
    frame = _ohlcv(closes, high_offset=6.0, low_offset=0.25)
    row = evaluate_symbol("TEST", frame)
    assert row.signal == Signal.HOLD_LOW_VOLUME
    assert row.cmf_value <= 0.05


def test_no_trade_in_downtrend():
    closes = 2000.0 - np.cumsum(np.tile([2.0, -1.0], 450))
    frame = _ohlcv(closes)
    row = evaluate_symbol("TEST", frame)
    assert row.signal == Signal.NO_TRADE
    assert row.bull_age_days is None


def test_no_trade_on_insufficient_history():
    frame = _ohlcv(_staircase_up(10))
    row = evaluate_symbol("TEST", frame)
    assert row.signal == Signal.NO_TRADE


def test_no_trade_when_too_few_bricks():
    # Enough candles for the indicators but a flat market forms no bricks.
    closes = 100.0 + 0.1 * np.sin(np.linspace(0, 20, 200))
    frame = _ohlcv(closes)
    row = evaluate_symbol("TEST", frame)
    assert row.signal == Signal.NO_TRADE
