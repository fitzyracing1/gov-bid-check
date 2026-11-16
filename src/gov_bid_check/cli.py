"""Command-line interface for gov-bid-check."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from gov_bid_check import __version__
from gov_bid_check.check import check_records
from gov_bid_check.parse import ParseError, parse_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gov-bid-check",
        description=(
            "Format pre-check for a draft bid or registration file (YAML, JSON, or CSV). "
            "Checks UEI, CAGE, NAICS shape, required fields, and deadlines. "
            "This is not legal advice or official verification, and it never calls SAM.gov."
        ),
    )
    parser.add_argument("file", help="Path to a YAML, JSON, or CSV draft")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the report to FILE.tidy.txt (never overwrites FILE)",
    )
    parser.add_argument(
        "--as-of",
        dest="as_of",
        help="Compare deadlines to this date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--ncage",
        action="store_true",
        help="Treat CAGE values as NCAGE (5 alphanumeric characters, no I/O).",
    )
    parser.add_argument("--version", action="version", version=f"gov-bid-check {__version__}")
    return parser


def _parse_as_of(value: str | None) -> date:
    if not value:
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    path = Path(args.file)
    try:
        as_of = _parse_as_of(args.as_of)
    except ValueError:
        print("gov-bid-check: --as-of must be YYYY-MM-DD", file=sys.stderr)
        return 2
    try:
        records = parse_path(path)
    except OSError as err:
        print(f"gov-bid-check: cannot read {path}: {err}", file=sys.stderr)
        return 1
    except (ParseError, ValueError) as err:
        from gov_bid_check.check import CheckResult

        result = CheckResult(source=str(path), parse_error=str(err))
        report = result.report()
        if args.write:
            dest = path.with_name(path.stem + ".tidy.txt")
            dest.write_text(report, encoding="utf-8")
            sys.stderr.write(f"Wrote {dest}\n")
        else:
            sys.stdout.write(report)
        return 1

    result = check_records(records, source=str(path), as_of=as_of, ncage=args.ncage)
    report = result.report()
    if args.write:
        dest = path.with_name(path.stem + ".tidy.txt")
        dest.write_text(report, encoding="utf-8")
        sys.stderr.write(f"Wrote {dest}\n")
    else:
        sys.stdout.write(report)
        if report and not report.endswith("\n"):
            sys.stdout.write("\n")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
