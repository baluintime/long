# NSE F&O Renko-Ichimoku Daily Screener (Enhanced Multi-Filter Version)

End-of-day screener for the NSE derivatives (F&O) universe implementing the
**PRD v2.0** dual-confirmation strategy:

| Verification Layer | Indicator | Condition for Entry Trigger |
|---|---|---|
| Layer 1: Structural Trend | ATR(14)-Renko + Ichimoku | Green brick closes above Kumo, Tenkan > Kijun, Chikou Span clear |
| Layer 2: Money Flow | Chaikin Money Flow (21) | CMF > +0.05 (institutional volume backup) |
| Layer 3: Exhaustion Check | RSI (14) on daily candles | RSI < 75 (not chased at an overbought peak) |

A stock only prints **`ENTER LONG`** when all three layers pass. Otherwise it
is classified as:

- **`HOLD-RSI EXHAUSTION`** — trend + volume confirmed but daily RSI(14) ≥ 75.
  Per the PRD, revisit only after a retracement takes RSI back below 70 while
  the Renko price stays above the Cloud.
- **`HOLD-LOW VOLUME`** — trend confirmed but CMF(21) ≤ +0.05 (a potential
  "Low-Volume Trap").
- **`NO TRADE`** — the structural trend layer itself is not satisfied.

## Output columns

| Field | Type | Purpose |
|---|---|---|
| Symbol | String | NSE ticker (e.g. RELIANCE, TCS) |
| Brick Size (ATR 14) | Float (INR) | Active volatility-normalized Renko brick size |
| CMF Value (21) | Float | Must be > +0.05 to validate volume backing |
| RSI (14) | Float | Daily candle RSI; must be < 75 |
| Signal Trigger | Enum | ENTER LONG / HOLD-RSI EXHAUSTION / HOLD-LOW VOLUME / NO TRADE |
| Bull-Age (Days) | Integer | Days since the initial breakout (recommended entry window: 1–4 days) |
| Kijun-sen Level | Float (INR) | Trailing stop-loss level for the manual F&O order |

## Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Run the nightly scan against the bundled F&O universe (data via Yahoo
Finance, `.NS` suffixed):

```bash
python -m renko_screener scan
```

Useful options:

```bash
# Scan a subset of symbols
python -m renko_screener scan --symbols RELIANCE TCS INFY

# Only print actionable rows (ENTER LONG) in the console table
python -m renko_screener scan --only-actionable

# Write the full report to CSV as well
python -m renko_screener scan --output report.csv

# Run offline from a directory of per-symbol OHLCV CSV files
# (files named <SYMBOL>.csv with Date,Open,High,Low,Close,Volume columns)
python -m renko_screener scan --source csv --csv-dir ./ohlcv
```

The F&O universe lives in `data/fo_universe.txt` (one symbol per line,
`#` comments allowed) — edit it as NSE adds/removes contracts.

## Methodology notes

- **Renko construction:** classic close-based Renko with a fixed brick size
  equal to the *latest* daily ATR(14) (volatility-normalized). A reversal
  requires two brick sizes of adverse movement.
- **Ichimoku:** computed **on the Renko brick series** (9/26/52), so the
  "green brick closes above Kumo" condition is evaluated in brick space.
  The Kumo at the current brick is the cloud projected 26 bricks earlier.
- **Chikou Span clear:** the current brick close is above the brick close 26
  bricks back (no price obstruction of the lagging span).
- **CMF(21) and RSI(14):** computed on the underlying *time-based* daily
  candlestick data, per the PRD.
- **Bull-Age:** calendar days elapsed since the date of the Renko brick on
  which the Layer-1 structural conditions first turned (and stayed) true.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Disclaimer

This tool is a research aid for **manual** F&O order placement. It does not
place orders and is not investment advice.
