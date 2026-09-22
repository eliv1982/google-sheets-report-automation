from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ConfigError, load_config
from src.google_sheets import GoogleSheetsClient, GoogleSheetsError

# Small, fixed connectivity-check range. This intentionally never reads a
# whole worksheet: a smoke test only needs to prove that authentication and
# read access work, not to dump worksheet contents.
DEFAULT_SAMPLE_RANGE = "A1:E5"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Bounded connectivity check for a specific worksheet. Reads only "
            f"the fixed range {DEFAULT_SAMPLE_RANGE} and never the full sheet."
        )
    )
    parser.add_argument(
        "worksheet",
        help="Exact name of the worksheet to check (required; no default is guessed).",
    )
    parser.add_argument(
        "--range",
        dest="range_reference",
        default=DEFAULT_SAMPLE_RANGE,
        help=f"A1 range within the worksheet to read (default: {DEFAULT_SAMPLE_RANGE}).",
    )
    parser.add_argument(
        "--show-values",
        action="store_true",
        help="Explicitly print the sample values read from the range. Off by default.",
    )
    return parser.parse_args(argv)


def _range(sheet_name: str, a1_notation: str) -> str:
    escaped_name = sheet_name.replace("'", "''")
    return f"'{escaped_name}'!{a1_notation}"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        config = load_config()
        client = GoogleSheetsClient.from_config(config)

        sheet_names = client.get_sheet_names()
        if args.worksheet not in sheet_names:
            print(
                f"Worksheet '{args.worksheet}' was not found in the configured spreadsheet.",
                file=sys.stderr,
            )
            return 1

        values = client.read_range(_range(args.worksheet, args.range_reference))
        print(
            f"Connected successfully. Read {len(values)} row(s) from "
            f"'{args.worksheet}'!{args.range_reference}."
        )

        if args.show_values:
            print(f"Sample values from '{args.worksheet}'!{args.range_reference}:")
            for row in values:
                print(row)
    except ConfigError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 1
    except GoogleSheetsError as error:
        print(f"Read smoke-test failed: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
