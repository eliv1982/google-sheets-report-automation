from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ConfigError, load_config
from src.google_sheets import GoogleSheetsClient, GoogleSheetsError


def _range(sheet_name: str, a1_notation: str) -> str:
    escaped_name = sheet_name.replace("'", "''")
    return f"'{escaped_name}'!{a1_notation}"


def main() -> int:
    client: GoogleSheetsClient | None = None
    temp_sheet_name = f"SmokeTest_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    sheet_created = False
    stage = "loading configuration"

    try:
        config = load_config()
        client = GoogleSheetsClient.from_config(config)

        stage = "creating temporary sheet"
        print(f"Creating temporary sheet: {temp_sheet_name}")
        client.create_sheet(temp_sheet_name)
        sheet_created = True

        stage = "writing test data"
        client.write_range(
            _range(temp_sheet_name, "A1:C3"),
            [
                ["Name", "Phone", "Notes"],
                ["Alice", "+7 999 123-45-67", "RAW input check"],
                ["Bob", "42", "Formatting smoke test"],
            ],
        )
        client.write_range(
            _range(temp_sheet_name, "A5:B5"),
            [["Merged area", ""]],
        )

        stage = "reading data back"
        values = client.read_range(_range(temp_sheet_name, "A1:C3"))
        if len(values) < 2 or len(values[1]) < 2:
            raise RuntimeError("Round-trip validation failed: expected test rows are missing.")
        if values[1][1] != "+7 999 123-45-67":
            raise RuntimeError(
                "Round-trip validation failed: '+'-prefixed value was not preserved as text."
            )

        stage = "formatting header"
        client.format_range(
            temp_sheet_name,
            0,
            1,
            0,
            3,
            background_color={"red": 0.9, "green": 0.95, "blue": 1.0},
            bold=True,
            horizontal_alignment="CENTER",
            vertical_alignment="MIDDLE",
            wrap_strategy="WRAP",
        )

        stage = "merging cells"
        client.merge_cells(temp_sheet_name, 4, 5, 0, 2)

        stage = "setting column widths"
        client.set_column_width(temp_sheet_name, 0, 3, 180)

        stage = "freezing header row"
        client.freeze_rows(temp_sheet_name, 1)

        print("Write smoke-test completed successfully.")
        return 0
    except ConfigError as error:
        print(f"Configuration error during write smoke-test: {error}", file=sys.stderr)
        return 1
    except (GoogleSheetsError, RuntimeError) as error:
        print(f"Write smoke-test failed during {stage}: {error}", file=sys.stderr)
        return 1
    finally:
        if sheet_created and client is not None:
            try:
                print(f"Cleaning up temporary sheet: {temp_sheet_name}")
                client.delete_sheet(temp_sheet_name)
            except GoogleSheetsError as cleanup_error:
                print(
                    f"Cleanup failed for temporary sheet {temp_sheet_name}: {cleanup_error}",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    raise SystemExit(main())
