"""Command-line interface for the nightly EOD scan."""

from __future__ import annotations

import argparse
import logging
import sys

from . import __version__, data, report, universe
from .signals import Signal, evaluate_symbol

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="renko_screener",
        description="NSE F&O Renko-Ichimoku daily screener (PRD v2.0): "
        "Ichimoku trend + CMF(21) volume + RSI(14) exhaustion filters.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="run the EOD scan and print the report")
    scan.add_argument(
        "--symbols",
        nargs="+",
        metavar="SYMBOL",
        help="scan only these NSE symbols (default: the bundled F&O universe)",
    )
    scan.add_argument(
        "--universe-file",
        help="path to an alternative universe file (one symbol per line)",
    )
    scan.add_argument(
        "--source",
        choices=["yahoo", "csv"],
        default="yahoo",
        help="data source (default: yahoo)",
    )
    scan.add_argument(
        "--csv-dir",
        help="directory of <SYMBOL>.csv OHLCV files (required with --source csv)",
    )
    scan.add_argument(
        "--period",
        default=data.DEFAULT_LOOKBACK,
        help=f"yahoo lookback period (default: {data.DEFAULT_LOOKBACK})",
    )
    scan.add_argument(
        "--only-actionable",
        action="store_true",
        help="print only ENTER LONG rows in the console table",
    )
    scan.add_argument("--output", help="also write the full report to this CSV path")
    scan.add_argument("-v", "--verbose", action="store_true", help="verbose logging")
    return parser


def run_scan(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.source == "csv" and not args.csv_dir:
        print("error: --csv-dir is required with --source csv", file=sys.stderr)
        return 2

    if args.symbols:
        symbols = [s.upper() for s in args.symbols]
    else:
        symbols = universe.load_universe(args.universe_file)

    rows = []
    skipped: list[str] = []
    for symbol in symbols:
        if args.source == "csv":
            ohlcv = data.load_csv(symbol, args.csv_dir)
        else:
            ohlcv = data.fetch_yahoo(symbol, period=args.period)
        if ohlcv is None:
            skipped.append(symbol)
            continue
        try:
            rows.append(evaluate_symbol(symbol, ohlcv))
        except Exception as exc:
            log.warning("evaluation failed for %s: %s", symbol, exc)
            skipped.append(symbol)

    frame = report.rows_to_frame(rows)
    print(report.render_console(frame, only_actionable=args.only_actionable))

    entries = int((frame["Signal Trigger"] == Signal.ENTER_LONG.value).sum()) if not frame.empty else 0
    print(
        f"\nScanned {len(rows)}/{len(symbols)} symbols | "
        f"ENTER LONG: {entries} | skipped (no data): {len(skipped)}"
    )
    if skipped:
        log.info("skipped symbols: %s", ", ".join(skipped))

    if args.output:
        report.write_csv(frame, args.output)
        print(f"Report written to {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "scan":
        return run_scan(args)
    return 2  # pragma: no cover - argparse enforces required subcommand
