"""Command-line entry point for the NSE Ichimoku position screener."""

from __future__ import annotations

import argparse
import logging
import sys

from . import __version__, data, report, universe
from .screener import scan

log = logging.getLogger(__name__)

#: Used when --output is passed without a path.
DEFAULT_OUTPUT = "ichimoku-{date}.xlsx"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nse-ichimoku",
        description=(
            "Fetch every NSE-listed stock and report which ones close above "
            "all Ichimoku lines and which close below all of them."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--symbols",
        nargs="+",
        metavar="SYMBOL",
        help="screen only these symbols instead of the full NSE universe",
    )
    parser.add_argument(
        "--universe-file",
        help="read the universe from a local file (one symbol per line, or EQUITY_L CSV)",
    )
    parser.add_argument(
        "--refresh-universe",
        action="store_true",
        help="ignore the cached NSE list and re-download it",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="fail instead of using the bundled partial list when NSE is unreachable",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="screen only the first N symbols of the universe (useful for a quick look)",
    )
    parser.add_argument(
        "--source",
        choices=["yahoo", "csv"],
        default="yahoo",
        help="price data source (default: yahoo)",
    )
    parser.add_argument(
        "--csv-dir", help="directory of <SYMBOL>.csv price files (with --source csv)"
    )
    parser.add_argument(
        "--period",
        default=data.DEFAULT_PERIOD,
        help=f"yahoo history window (default: {data.DEFAULT_PERIOD})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=data.DEFAULT_BATCH_SIZE,
        help=f"symbols per download batch (default: {data.DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--show-mixed",
        action="store_true",
        help="also list stocks whose close is tangled in the lines",
    )
    parser.add_argument(
        "--fresh-only",
        action="store_true",
        help="drop symbols whose latest bar lags the rest of the market",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="print the full table of Ichimoku values instead of just names",
    )
    parser.add_argument(
        "--output",
        nargs="?",
        const=DEFAULT_OUTPUT,
        help="write the full scan to this path; .xlsx gives a formatted Excel "
        "workbook, .csv a flat file. A {date} placeholder expands to the session "
        f"date. Passed with no value, writes {DEFAULT_OUTPUT}",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose logging")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.source == "csv" and not args.csv_dir:
        print("error: --csv-dir is required with --source csv", file=sys.stderr)
        return 2

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols]
        source = "command line"
    else:
        try:
            loaded = universe.load_universe(
                args.universe_file,
                refresh=args.refresh_universe,
                allow_fallback=not args.no_fallback,
            )
        except Exception as exc:
            print(f"error: could not load the NSE universe: {exc}", file=sys.stderr)
            return 1
        symbols, source = loaded.symbols, loaded.source
        if source == "bundled":
            print(
                "warning: NSE was unreachable — screening the bundled partial list "
                "of liquid stocks, not the full exchange universe.\n",
                file=sys.stderr,
            )

    if args.limit:
        symbols = symbols[: args.limit]
    if not symbols:
        print("error: universe is empty", file=sys.stderr)
        return 1

    if args.source == "csv":
        price_data = data.load_csv_dir(symbols, args.csv_dir)
    else:
        price_data = data.fetch_yahoo_batch(
            symbols, period=args.period, batch_size=args.batch_size
        )

    result = scan(price_data)
    result.skipped.extend(sorted(set(symbols) - set(price_data)))
    if args.fresh_only:
        result = result.drop_stale()

    warning = report.freshness_warning(result)
    if warning:
        print(warning + "\n", file=sys.stderr)

    print(report.as_of_line(result) + "\n")
    if args.detail:
        print(report.render_detail(result, show_mixed=args.show_mixed))
    else:
        print(report.render_names(result, show_mixed=args.show_mixed))

    print("\n" + report.summary_line(result, len(symbols), source))

    if args.output:
        out_path = report.resolve_output_path(args.output, result)
        try:
            written = report.write_results(result, out_path, len(symbols), source)
        except ImportError:
            print(
                "error: writing .xlsx needs openpyxl — pip install openpyxl "
                "(or use a .csv path)",
                file=sys.stderr,
            )
            return 1
        print(f"Full results written to {written}")
    return 0
