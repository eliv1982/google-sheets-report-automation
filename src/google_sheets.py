from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Sequence

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config import AppConfig


class GoogleSheetsError(RuntimeError):
    """Base exception for Google Sheets client errors."""


class GoogleSheetsValidationError(GoogleSheetsError):
    """Raised when provided client arguments are invalid."""


class GoogleSheetsAPIError(GoogleSheetsError):
    """Raised when a Google Sheets API request fails."""


class SheetNotFoundError(GoogleSheetsError):
    """Raised when a sheet with the requested name does not exist."""


class SheetAlreadyExistsError(GoogleSheetsError):
    """Raised when attempting to create a duplicate sheet."""


class GoogleSheetsClient:
    DEFAULT_SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)
    SPREADSHEET_METADATA_FIELDS = "sheets(properties(sheetId,title,gridProperties))"

    # Only failures that are safe to retry without risking duplicate side
    # effects: rate limiting and transient server errors.
    RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
    DEFAULT_MAX_RETRY_ATTEMPTS = 3
    DEFAULT_RETRY_DELAYS_SECONDS = (0.5, 1.0)

    def __init__(
        self,
        spreadsheet_id: str,
        credentials_path: str | Path,
        scopes: Sequence[str] | None = None,
        service: Any | None = None,
        service_builder: Any = build,
        max_retry_attempts: int = DEFAULT_MAX_RETRY_ATTEMPTS,
        retry_delays_seconds: Sequence[float] | None = None,
        retry_sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = Path(credentials_path)
        self.scopes = tuple(scopes or self.DEFAULT_SCOPES)
        self._service = service
        self._service_builder = service_builder
        self._max_retry_attempts = max(1, max_retry_attempts)
        self._retry_delays_seconds = tuple(
            retry_delays_seconds
            if retry_delays_seconds is not None
            else self.DEFAULT_RETRY_DELAYS_SECONDS
        )
        self._sleep = retry_sleep or time.sleep

    @classmethod
    def from_config(
        cls, config: AppConfig, scopes: Sequence[str] | None = None
    ) -> "GoogleSheetsClient":
        return cls(
            spreadsheet_id=config.spreadsheet_id,
            credentials_path=config.credentials_path,
            scopes=scopes,
        )

    def _get_service(self) -> Any:
        if self._service is None:
            credentials = Credentials.from_service_account_file(
                str(self.credentials_path),
                scopes=list(self.scopes),
            )
            self._service = self._service_builder(
                "sheets",
                "v4",
                credentials=credentials,
                cache_discovery=False,
            )
        return self._service

    def _spreadsheets_resource(self) -> Any:
        return self._get_service().spreadsheets()

    def _values_resource(self) -> Any:
        return self._spreadsheets_resource().values()

    def _execute(self, request: Any, action: str, *, retryable: bool = False) -> Any:
        """Execute a request, retrying a bounded number of times only when
        ``retryable`` is set and the failure is a clearly transient one
        (HTTP 429 or 5xx). Non-retryable or exhausted failures are wrapped
        and raised as GoogleSheetsAPIError.
        """
        attempt = 0
        while True:
            attempt += 1
            try:
                return request.execute()
            except HttpError as error:
                status_code = getattr(error.resp, "status", None)
                can_retry = (
                    retryable
                    and status_code in self.RETRYABLE_STATUS_CODES
                    and attempt < self._max_retry_attempts
                )
                if can_retry:
                    delay_index = min(attempt - 1, len(self._retry_delays_seconds) - 1)
                    self._sleep(self._retry_delays_seconds[delay_index])
                    continue
                display_status = status_code if status_code is not None else "unknown"
                raise GoogleSheetsAPIError(
                    f"Google Sheets API request failed while {action}. "
                    f"HTTP status: {display_status}."
                ) from error

    def _get_spreadsheet_metadata(self) -> dict[str, Any]:
        request = self._spreadsheets_resource().get(
            spreadsheetId=self.spreadsheet_id,
            includeGridData=False,
            fields=self.SPREADSHEET_METADATA_FIELDS,
        )
        return self._execute(request, "fetching spreadsheet metadata", retryable=True)

    def _validate_sheet_name(self, sheet_name: str) -> None:
        if not sheet_name or not sheet_name.strip():
            raise GoogleSheetsValidationError("Sheet name must not be empty.")

    def _validate_range_name(self, range_name: str) -> None:
        if not range_name or not range_name.strip():
            raise GoogleSheetsValidationError("Range name must not be empty.")

    def _normalize_values(self, values: Sequence[Sequence[Any]]) -> list[list[Any]]:
        if isinstance(values, (str, bytes)):
            raise GoogleSheetsValidationError("Values must be a two-dimensional array.")

        normalized_values: list[list[Any]] = []
        for row in values:
            if isinstance(row, (str, bytes)):
                raise GoogleSheetsValidationError("Each row must be a sequence of cell values.")
            normalized_values.append(list(row))
        return normalized_values

    def _validate_index_range(self, start: int, end: int, label: str) -> None:
        if start < 0 or end < 0:
            raise GoogleSheetsValidationError(
                f"{label.capitalize()} indexes must be zero-based and non-negative."
            )
        if end <= start:
            raise GoogleSheetsValidationError(
                f"{label.capitalize()} end index must be greater than start index."
            )

    def _get_sheet_properties(self, sheet_name: str) -> dict[str, Any]:
        self._validate_sheet_name(sheet_name)
        metadata = self._get_spreadsheet_metadata()

        for sheet in metadata.get("sheets", []):
            properties = sheet.get("properties", {})
            if properties.get("title") == sheet_name:
                return properties

        raise SheetNotFoundError(f"Sheet '{sheet_name}' was not found.")

    def _build_grid_range(
        self,
        sheet_id: int,
        start_row: int,
        end_row: int,
        start_column: int,
        end_column: int,
    ) -> dict[str, int]:
        """Build a GridRange using zero-based, end-exclusive indexes."""
        self._validate_index_range(start_row, end_row, "row")
        self._validate_index_range(start_column, end_column, "column")

        return {
            "sheetId": sheet_id,
            "startRowIndex": start_row,
            "endRowIndex": end_row,
            "startColumnIndex": start_column,
            "endColumnIndex": end_column,
        }

    def _batch_update(
        self, requests: list[dict[str, Any]], action: str, *, retryable: bool
    ) -> dict[str, Any]:
        request = self._spreadsheets_resource().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"requests": requests},
        )
        return self._execute(request, action, retryable=retryable)

    def get_sheet_names(self) -> list[str]:
        metadata = self._get_spreadsheet_metadata()
        sheets = metadata.get("sheets", [])
        return [
            sheet.get("properties", {}).get("title", "")
            for sheet in sheets
            if sheet.get("properties", {}).get("title")
        ]

    def get_sheet_id(self, sheet_name: str) -> int:
        properties = self._get_sheet_properties(sheet_name)
        sheet_id = properties.get("sheetId")
        if sheet_id is None:
            raise GoogleSheetsAPIError(
                f"Sheet '{sheet_name}' does not expose a valid sheetId."
            )
        return int(sheet_id)

    def read_range(self, range_name: str) -> list[list[Any]]:
        self._validate_range_name(range_name)
        request = self._values_resource().get(
            spreadsheetId=self.spreadsheet_id,
            range=range_name,
        )
        response = self._execute(request, f"reading range '{range_name}'", retryable=True)
        return response.get("values", [])

    def read_all_values(self, sheet_name: str) -> list[list[Any]]:
        return self.read_range(self._format_sheet_range(sheet_name))

    def create_sheet(self, sheet_name: str) -> int:
        self._validate_sheet_name(sheet_name)
        if sheet_name in self.get_sheet_names():
            raise SheetAlreadyExistsError(f"Sheet '{sheet_name}' already exists.")

        # Worksheet creation is not idempotent: retrying it after an
        # ambiguous failure could create duplicate sheets, so this call is
        # never automatically retried.
        response = self._batch_update(
            requests=[{"addSheet": {"properties": {"title": sheet_name}}}],
            action=f"creating sheet '{sheet_name}'",
            retryable=False,
        )
        replies = response.get("replies", [])
        sheet_id = (
            replies[0]
            .get("addSheet", {})
            .get("properties", {})
            .get("sheetId")
            if replies
            else None
        )
        if sheet_id is None:
            raise GoogleSheetsAPIError(
                f"Google Sheets API did not return sheetId for sheet '{sheet_name}'."
            )
        return int(sheet_id)

    def delete_sheet(self, sheet_name: str) -> dict[str, Any]:
        return self._batch_update(
            requests=[{"deleteSheet": {"sheetId": self.get_sheet_id(sheet_name)}}],
            action=f"deleting sheet '{sheet_name}'",
            retryable=True,
        )

    def delete_sheet_by_id(self, sheet_id: int) -> dict[str, Any]:
        """Delete a sheet by its already-known numeric id, avoiding an extra
        metadata lookup. Deletion is safe to retry on transient failures.
        """
        return self._batch_update(
            requests=[{"deleteSheet": {"sheetId": sheet_id}}],
            action=f"deleting sheet id {sheet_id}",
            retryable=True,
        )

    def write_range(
        self, range_name: str, values: Sequence[Sequence[Any]]
    ) -> dict[str, Any]:
        self._validate_range_name(range_name)
        request = self._values_resource().update(
            spreadsheetId=self.spreadsheet_id,
            range=range_name,
            valueInputOption="RAW",
            body={"values": self._normalize_values(values)},
        )
        return self._execute(request, f"writing range '{range_name}'", retryable=True)

    def batch_write_ranges(
        self,
        data: Sequence[tuple[str, Sequence[Sequence[Any]]]],
        action: str = "writing batched ranges",
    ) -> dict[str, Any]:
        """Write several fixed ranges in a single values.batchUpdate call."""
        if not data:
            raise GoogleSheetsValidationError("At least one range must be provided.")

        value_ranges: list[dict[str, Any]] = []
        for range_name, values in data:
            self._validate_range_name(range_name)
            value_ranges.append(
                {"range": range_name, "values": self._normalize_values(values)}
            )

        request = self._values_resource().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"valueInputOption": "RAW", "data": value_ranges},
        )
        return self._execute(request, action, retryable=True)

    def append_rows(
        self, range_name: str, values: Sequence[Sequence[Any]]
    ) -> dict[str, Any]:
        self._validate_range_name(range_name)
        request = self._values_resource().append(
            spreadsheetId=self.spreadsheet_id,
            range=range_name,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": self._normalize_values(values)},
        )
        return self._execute(request, f"appending rows to range '{range_name}'")

    def clear_range(self, range_name: str) -> dict[str, Any]:
        self._validate_range_name(range_name)
        request = self._values_resource().clear(
            spreadsheetId=self.spreadsheet_id,
            range=range_name,
            body={},
        )
        return self._execute(request, f"clearing range '{range_name}'", retryable=True)

    def batch_update(
        self,
        requests: Sequence[dict[str, Any]],
        action: str = "applying batched updates",
    ) -> dict[str, Any]:
        """Send several formatting/dimension/merge requests in a single
        spreadsheets.batchUpdate call.
        """
        if not requests:
            raise GoogleSheetsValidationError("At least one request must be provided.")
        return self._batch_update(list(requests), action, retryable=True)

    def _build_user_entered_format(
        self,
        *,
        background_color: dict[str, float] | None = None,
        bold: bool | None = None,
        font_size: int | None = None,
        horizontal_alignment: str | None = None,
        vertical_alignment: str | None = None,
        wrap_strategy: str | None = None,
        number_format: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], list[str]]:
        user_entered_format: dict[str, Any] = {}
        fields: list[str] = []

        if background_color is not None:
            user_entered_format["backgroundColor"] = background_color
            fields.append("userEnteredFormat.backgroundColor")

        text_format: dict[str, Any] = {}
        if bold is not None:
            text_format["bold"] = bold
            fields.append("userEnteredFormat.textFormat.bold")
        if font_size is not None:
            text_format["fontSize"] = font_size
            fields.append("userEnteredFormat.textFormat.fontSize")
        if text_format:
            user_entered_format["textFormat"] = text_format

        if horizontal_alignment is not None:
            user_entered_format["horizontalAlignment"] = horizontal_alignment
            fields.append("userEnteredFormat.horizontalAlignment")

        if vertical_alignment is not None:
            user_entered_format["verticalAlignment"] = vertical_alignment
            fields.append("userEnteredFormat.verticalAlignment")

        if wrap_strategy is not None:
            user_entered_format["wrapStrategy"] = wrap_strategy
            fields.append("userEnteredFormat.wrapStrategy")

        if number_format is not None:
            user_entered_format["numberFormat"] = number_format
            fields.append("userEnteredFormat.numberFormat")

        return user_entered_format, fields

    def build_format_request(
        self,
        sheet_id: int,
        start_row: int,
        end_row: int,
        start_column: int,
        end_column: int,
        *,
        background_color: dict[str, float] | None = None,
        bold: bool | None = None,
        font_size: int | None = None,
        horizontal_alignment: str | None = None,
        vertical_alignment: str | None = None,
        wrap_strategy: str | None = None,
        number_format: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Build a repeatCell formatting request for an already-known sheet id."""
        user_entered_format, fields = self._build_user_entered_format(
            background_color=background_color,
            bold=bold,
            font_size=font_size,
            horizontal_alignment=horizontal_alignment,
            vertical_alignment=vertical_alignment,
            wrap_strategy=wrap_strategy,
            number_format=number_format,
        )
        if not fields:
            raise GoogleSheetsValidationError(
                "At least one formatting property must be provided."
            )

        return {
            "repeatCell": {
                "range": self._build_grid_range(
                    sheet_id, start_row, end_row, start_column, end_column
                ),
                "cell": {"userEnteredFormat": user_entered_format},
                "fields": ",".join(fields),
            }
        }

    def format_range(
        self,
        sheet_name: str,
        start_row: int,
        end_row: int,
        start_column: int,
        end_column: int,
        *,
        background_color: dict[str, float] | None = None,
        bold: bool | None = None,
        font_size: int | None = None,
        horizontal_alignment: str | None = None,
        vertical_alignment: str | None = None,
        wrap_strategy: str | None = None,
        number_format: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Format a range using zero-based, end-exclusive GridRange indexes."""
        if not any(
            value is not None
            for value in (
                background_color,
                bold,
                font_size,
                horizontal_alignment,
                vertical_alignment,
                wrap_strategy,
                number_format,
            )
        ):
            raise GoogleSheetsValidationError(
                "At least one formatting property must be provided."
            )

        sheet_id = self.get_sheet_id(sheet_name)
        request = self.build_format_request(
            sheet_id,
            start_row,
            end_row,
            start_column,
            end_column,
            background_color=background_color,
            bold=bold,
            font_size=font_size,
            horizontal_alignment=horizontal_alignment,
            vertical_alignment=vertical_alignment,
            wrap_strategy=wrap_strategy,
            number_format=number_format,
        )
        return self._batch_update(
            [request], action=f"formatting range on sheet '{sheet_name}'", retryable=True
        )

    def build_merge_request(
        self,
        sheet_id: int,
        start_row: int,
        end_row: int,
        start_column: int,
        end_column: int,
    ) -> dict[str, Any]:
        return {
            "mergeCells": {
                "range": self._build_grid_range(
                    sheet_id, start_row, end_row, start_column, end_column
                ),
                "mergeType": "MERGE_ALL",
            }
        }

    def merge_cells(
        self,
        sheet_name: str,
        start_row: int,
        end_row: int,
        start_column: int,
        end_column: int,
    ) -> dict[str, Any]:
        """Merge cells using zero-based, end-exclusive GridRange indexes."""
        sheet_id = self.get_sheet_id(sheet_name)
        request = self.build_merge_request(
            sheet_id, start_row, end_row, start_column, end_column
        )
        return self._batch_update(
            [request], action=f"merging cells on sheet '{sheet_name}'", retryable=True
        )

    def build_unmerge_request(
        self,
        sheet_id: int,
        start_row: int,
        end_row: int,
        start_column: int,
        end_column: int,
    ) -> dict[str, Any]:
        return {
            "unmergeCells": {
                "range": self._build_grid_range(
                    sheet_id, start_row, end_row, start_column, end_column
                )
            }
        }

    def unmerge_cells(
        self,
        sheet_name: str,
        start_row: int,
        end_row: int,
        start_column: int,
        end_column: int,
    ) -> dict[str, Any]:
        """Unmerge cells using zero-based, end-exclusive GridRange indexes."""
        sheet_id = self.get_sheet_id(sheet_name)
        request = self.build_unmerge_request(
            sheet_id, start_row, end_row, start_column, end_column
        )
        return self._batch_update(
            [request], action=f"unmerging cells on sheet '{sheet_name}'", retryable=True
        )

    def build_column_width_request(
        self,
        sheet_id: int,
        start_column: int,
        end_column: int,
        width_pixels: int,
    ) -> dict[str, Any]:
        if width_pixels <= 0:
            raise GoogleSheetsValidationError("Column width must be greater than zero.")
        self._validate_index_range(start_column, end_column, "column")

        return {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": start_column,
                    "endIndex": end_column,
                },
                "properties": {"pixelSize": width_pixels},
                "fields": "pixelSize",
            }
        }

    def set_column_width(
        self,
        sheet_name: str,
        start_column: int,
        end_column: int,
        width_pixels: int,
    ) -> dict[str, Any]:
        if width_pixels <= 0:
            raise GoogleSheetsValidationError("Column width must be greater than zero.")
        self._validate_index_range(start_column, end_column, "column")

        sheet_id = self.get_sheet_id(sheet_name)
        request = self.build_column_width_request(
            sheet_id, start_column, end_column, width_pixels
        )
        return self._batch_update(
            [request],
            action=f"setting column width on sheet '{sheet_name}'",
            retryable=True,
        )

    def build_row_height_request(
        self,
        sheet_id: int,
        start_row: int,
        end_row: int,
        height_pixels: int,
    ) -> dict[str, Any]:
        if height_pixels <= 0:
            raise GoogleSheetsValidationError("Row height must be greater than zero.")
        self._validate_index_range(start_row, end_row, "row")

        return {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": start_row,
                    "endIndex": end_row,
                },
                "properties": {"pixelSize": height_pixels},
                "fields": "pixelSize",
            }
        }

    def set_row_height(
        self,
        sheet_name: str,
        start_row: int,
        end_row: int,
        height_pixels: int,
    ) -> dict[str, Any]:
        if height_pixels <= 0:
            raise GoogleSheetsValidationError("Row height must be greater than zero.")
        self._validate_index_range(start_row, end_row, "row")

        sheet_id = self.get_sheet_id(sheet_name)
        request = self.build_row_height_request(sheet_id, start_row, end_row, height_pixels)
        return self._batch_update(
            [request], action=f"setting row height on sheet '{sheet_name}'", retryable=True
        )

    def build_freeze_rows_request(self, sheet_id: int, row_count: int) -> dict[str, Any]:
        if row_count < 0:
            raise GoogleSheetsValidationError("Frozen row count must not be negative.")

        return {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": row_count},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        }

    def freeze_rows(self, sheet_name: str, row_count: int) -> dict[str, Any]:
        if row_count < 0:
            raise GoogleSheetsValidationError("Frozen row count must not be negative.")

        sheet_id = self.get_sheet_id(sheet_name)
        request = self.build_freeze_rows_request(sheet_id, row_count)
        return self._batch_update(
            [request], action=f"freezing rows on sheet '{sheet_name}'", retryable=True
        )

    @staticmethod
    def _format_sheet_range(sheet_name: str) -> str:
        escaped_name = sheet_name.replace("'", "''")
        return f"'{escaped_name}'"
