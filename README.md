# NSE Ichimoku Position Screener

Fetches every stock listed on the NSE, computes the Ichimoku Kinko Hyo lines
for each one, and prints the names of the stocks whose latest close sits
**above all** the Ichimoku lines, and those whose close sits **below all** of
them.

That is the whole tool — one question, asked across the entire exchange.

## What "above all Ichimoku" means

Ichimoku plots four lines at the current bar (standard 9 / 26 / 52 settings,
cloud displaced 26 bars forward):

| Line | Definition |
|---|---|
| Tenkan-sen | (9-bar highest high + lowest low) / 2 |
| Kijun-sen | (26-bar highest high + lowest low) / 2 |
| Senkou Span A | (Tenkan + Kijun) / 2, plotted 26 bars ahead |
| Senkou Span B | (52-bar highest high + lowest low) / 2, plotted 26 bars ahead |

A stock is classified as:

- **ABOVE** — the close is greater than *every* one of the four lines
  (above both the Tenkan and Kijun, and clear above the whole cloud).
- **BELOW** — the close is less than every one of them.
- **MIXED** — anything else: inside the cloud, or tangled between the lines.
  Hidden by default; pass `--show-mixed` to list these too.

The Chikou Span (close plotted 26 bars back) is reported as a `Chikou Clear`
flag in the detailed view, but it does not affect the classification.

A stock needs at least 78 daily bars for a fully-formed cloud, so recent
listings are reported as skipped rather than guessed at.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python -m nse_ichimoku
```

That downloads the full NSE equity list, pulls a year of daily candles for
each symbol from Yahoo Finance, and prints the two lists of names:

```
ABOVE ALL ICHIMOKU LINES — bullish (5 stocks)
  HDFCBANK  INFY      RELIANCE  TCS       WIPRO

BELOW ALL ICHIMOKU LINES — bearish (3 stocks)
  SBIN       TATASTEEL  VEDL

Universe: 2114 NSE symbols (source: nse) | evaluated: 1987 | above: 5 | below: 3 | mixed: 1979 | skipped (no/short data): 127
```

Options worth knowing:

```bash
# Show the Ichimoku values behind the classification
python -m nse_ichimoku --detail

# Include the stocks tangled in the lines
python -m nse_ichimoku --show-mixed

# Just a few symbols
python -m nse_ichimoku --symbols RELIANCE TCS INFY

# Try a slice of the exchange first — a full scan takes a while
python -m nse_ichimoku --limit 200

# Save results
python -m nse_ichimoku --output ichimoku.csv

# Re-download the NSE list instead of using the day-old cache
python -m nse_ichimoku --refresh-universe

# Run offline against a directory of <SYMBOL>.csv files (Date,Open,High,Low,Close)
python -m nse_ichimoku --universe-file symbols.txt --source csv --csv-dir ./prices
```

## Where the universe comes from

The stock list is NSE's own master file, `EQUITY_L.csv`, filtered to the `EQ`
and `BE` series (the actual equity segments — debt instruments, ETFs and
warrants are left out). NSE only serves it to browser-like clients, so the
screener primes a session with cookies before requesting the file, then
caches the result in `data/` for a day.

If NSE is unreachable, the screener falls back to the bundled snapshot in
`data/nse_equity_list.csv` — around 200 liquid names, not the whole exchange
— and prints a warning saying so. Pass `--no-fallback` to make an
unreachable NSE a hard error instead.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Notes

A full-exchange scan pulls history for roughly two thousand symbols, so it
takes a few minutes and is rate-limit sensitive; `--batch-size` tunes how
many tickers go in each Yahoo request. This is a research aid, not
investment advice — it places no orders.
