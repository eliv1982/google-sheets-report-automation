from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ConfigError, load_config
from src.google_sheets import GoogleSheetsClient


def main() -> int:
    try:
        config = load_config()
        client = GoogleSheetsClient.from_config(config)

        sheet_names = client.get_sheet_names()
        if not sheet_names:
            print("No sheets found.")
            return 0

        print("Sheet names:")
        for sheet_name in sheet_names:
            print(sheet_name)

        print()
        print(f"First 5 rows from: {sheet_names[0]}")
        for row in client.read_all_values(sheet_names[0])[:5]:
            print(row)
    except ConfigError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
