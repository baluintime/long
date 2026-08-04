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
Ichimoku positions as of 2026-08-04 (latest NSE daily close)

ABOVE ALL ICHIMOKU LINES — bullish (5 stocks)
  HDFCBANK  INFY      RELIANCE  TCS       WIPRO

BELOW ALL ICHIMOKU LINES — bearish (3 stocks)
  SBIN       TATASTEEL  VEDL

Universe: 2114 NSE symbols (source: nse) | evaluated: 1987 | above: 5 | below: 3 | mixed: 1979 | skipped (no/short data): 127
```

## Running it once a day after the close

The screener works on daily candles and is built to be run once per session,
after the market closes. Two things keep that honest:

**The as-of line names the session.** Every run states which trading day the
result describes, so you are never guessing whether you are looking at
today's close or yesterday's.

**A stale scan announces itself.** NSE closes at 3:30 PM IST, but the daily
bar reaches the data feed some time later. If you run too early, on a
weekend, or on a market holiday, the newest available bar is not today's —
so the screener prints a warning to stderr before the results:

```
warning: the latest daily bar is 2026-07-15, 20 days behind today (2026-08-04 IST).
Market holiday or weekend, or the price feed has not published today's close yet —
re-run later if you expected today's session.
```

Individual stocks can also lag the market — a halted or suspended counter
keeps its last traded bar while everything else moves on. Those are counted
as `lagging the session` in the summary, and `--fresh-only` drops them so
the lists contain only stocks that actually traded in the session:

```bash
python -m nse_ichimoku --fresh-only --output scans/ichimoku-{date}.csv
```

The `{date}` placeholder expands to the session date, so each day's run
lands in its own file instead of overwriting yesterday's.

Give the feed some room after the close — running around an hour later is
comfortable — and check the as-of line matches the session you expect.
The NSE stock list itself is cached for a day, so a once-daily run picks up
newly listed symbols without re-downloading the master file on retries.

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

# Save results (use {date} to keep one file per session)
python -m nse_ichimoku --output ichimoku-{date}.csv

# Ignore stocks whose last bar lags the rest of the market
python -m nse_ichimoku --fresh-only

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
