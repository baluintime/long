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
each symbol from Yahoo Finance, writes `ichimoku-<session-date>.xlsx`, and
prints the two lists of names:

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
python -m nse_ichimoku --fresh-only --output scans/ichimoku-{date}.xlsx
```

The `{date}` placeholder expands to the session date, so each day's run
lands in its own file instead of overwriting yesterday's.

## The Excel workbook

`--output` writes an `.xlsx` workbook holding the complete scan — every
stock, not just the two headline lists:

Every run writes one, with no flag needed — `python -m nse_ichimoku` alone
produces `ichimoku-<session-date>.xlsx` in the current directory. Use
`--output` for a different path, or `--no-file` to print to the console only.

| Sheet | Contents |
|---|---|
| Summary | Session date, run time, universe size and source, and the counts |
| Above | Stocks above every line, widest cushion first |
| Below | Stocks below every line, deepest first |
| Mixed | Stocks tangled in the lines |
| All | Every classified stock, alphabetical |
| Skipped | Every symbol that could not be classified, and why |

Between `All` and `Skipped`, every symbol in the universe is accounted for
by name. A stock never disappears without explanation: the `Skipped` sheet
gives the reason — `no price data`, `insufficient history: 40 of 78 daily
bars`, `lagging the session`, and so on.

Each row carries the raw levels *and* the percentage gap between the close
and every line:

| Column | Meaning |
|---|---|
| Close, Tenkan, Kijun, Senkou A, Senkou B | The levels themselves, in INR |
| Cloud Top / Cloud Bottom | The higher and lower of Senkou A and B |
| % vs Tenkan / Kijun / Senkou A / Senkou B | `(Close − Line) / Line × 100` |
| % vs Cloud Top / Cloud Bottom | The same, against the cloud edges |
| % to Nearest Line | The signed gap to whichever line is closest |
| Chikou Clear | Whether the lagging span confirms the position |

The sign convention is uniform: **positive means the close is above that
level**, so an ABOVE stock shows positive percentages across the row and a
BELOW stock negative ones.

`% to Nearest Line` is the one to sort by. For a stock above the cloud it
is the cushion before price breaks back into the lines — a name sitting
+0.4% above its Tenkan is a very different proposition from one sitting
+12% above everything, even though both are simply "ABOVE".

The sheets arrive frozen, auto-filtered, and formatted, so you can sort and
filter the moment you open the file. Pass a `.csv` path instead if you want
a flat file — same columns, single sheet.

Give the feed some room after the close — running around an hour later is
comfortable — and check the as-of line matches the session you expect.
The NSE stock list itself is cached for a day, so a once-daily run picks up
newly listed symbols without re-downloading the master file on retries.

Options worth knowing:

```bash
# Show how far each close sits from every line, in %
python -m nse_ichimoku --detail

# Include the stocks tangled in the lines
python -m nse_ichimoku --show-mixed

# Just a few symbols
python -m nse_ichimoku --symbols RELIANCE TCS INFY

# Try a slice of the exchange first — a full scan takes a while
python -m nse_ichimoku --limit 200

# Write the workbook somewhere else ({date} keeps one file per session)
python -m nse_ichimoku --output scans/ichimoku-{date}.xlsx

# Console only, no file
python -m nse_ichimoku --no-file

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

## Troubleshooting

**"Excel cannot open the file … because the file format or file extension is
not valid."**

The file is not really an `.xlsx`. Check what it actually is:

```bash
file ichimoku-*.xlsx          # macOS / Linux
```

A healthy workbook reports `Microsoft Excel 2007+`. If it says `CSV ASCII
text`, the file was written by a version of this tool older than Excel
support — update and re-run:

```bash
git pull
pip install -r requirements.txt   # brings in openpyxl
python -m nse_ichimoku
```

Every run now prints the format it wrote (`Excel workbook written to …`),
and the workbook is verified before it is put in place, so a failed run
leaves the previous day's file untouched rather than a corrupt one.

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
