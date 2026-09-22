from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from src.google_sheets import (
    GoogleSheetsAPIError,
    GoogleSheetsClient,
    GoogleSheetsValidationError,
    SheetAlreadyExistsError,
    SheetNotFoundError,
)


def _http_error(status: int) -> HttpError:
    return HttpError(
        resp=SimpleNamespace(status=status, reason="error"),
        content=b"{}",
    )


def _build_client_with_mocks():
    credentials = object()
    service = MagicMock()
    spreadsheets = service.spreadsheets.return_value
    values = spreadsheets.values.return_value
    service_builder = MagicMock(return_value=service)

    return credentials, service, spreadsheets, values, service_builder


def _build_client_with_service(retry_sleep=None):
    service = MagicMock()
    spreadsheets = service.spreadsheets.return_value
    values = spreadsheets.values.return_value
    client = GoogleSheetsClient(
        spreadsheet_id="spreadsheet-id",
        credentials_path="credentials/service-account.json",
        service=service,
        retry_sleep=retry_sleep,
    )
    return client, service, spreadsheets, values


def test_get_sheet_names_returns_titles() -> None:
    credentials, _, spreadsheets, _, service_builder = _build_client_with_mocks()
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [
            {"properties": {"title": "Summary"}},
            {"properties": {"title": "Raw Data"}},
        ]
    }
    with patch(
        "src.google_sheets.Credentials.from_service_account_file",
        return_value=credentials,
    ):
        client = GoogleSheetsClient(
            spreadsheet_id="spreadsheet-id",
            credentials_path="credentials/service-account.json",
            service_builder=service_builder,
        )
        result = client.get_sheet_names()

    assert result == ["Summary", "Raw Data"]
    service_builder.assert_called_once_with(
        "sheets",
        "v4",
        credentials=credentials,
        cache_discovery=False,
    )


def test_read_range_returns_values() -> None:
    credentials, _, _, values, service_builder = _build_client_with_mocks()
    values.get.return_value.execute.return_value = {
        "values": [["Name", "Score"], ["Alice", "42"]]
    }
    with patch(
        "src.google_sheets.Credentials.from_service_account_file",
        return_value=credentials,
    ):
        client = GoogleSheetsClient(
            spreadsheet_id="spreadsheet-id",
            credentials_path="credentials/service-account.json",
            service_builder=service_builder,
        )
        result = client.read_range("Sheet1!A1:B2")

    assert result == [["Name", "Score"], ["Alice", "42"]]
    values.get.assert_called_once_with(
        spreadsheetId="spreadsheet-id",
        range="Sheet1!A1:B2",
    )


def test_read_all_values_reads_full_sheet() -> None:
    credentials, _, _, values, service_builder = _build_client_with_mocks()
    values.get.return_value.execute.return_value = {
        "values": [["A", "B"], ["1", "2"]]
    }
    with patch(
        "src.google_sheets.Credentials.from_service_account_file",
        return_value=credentials,
    ):
        client = GoogleSheetsClient(
            spreadsheet_id="spreadsheet-id",
            credentials_path="credentials/service-account.json",
            service_builder=service_builder,
        )
        result = client.read_all_values("Quarterly Report")

    assert result == [["A", "B"], ["1", "2"]]
    values.get.assert_called_once_with(
        spreadsheetId="spreadsheet-id",
        range="'Quarterly Report'",
    )


def test_get_sheet_id_returns_numeric_id() -> None:
    client, _, spreadsheets, _ = _build_client_with_service()
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Summary", "sheetId": 321}}]
    }

    result = client.get_sheet_id("Summary")

    assert result == 321


def test_create_sheet_creates_new_sheet() -> None:
    client, _, spreadsheets, _ = _build_client_with_service()
    spreadsheets.get.return_value.execute.return_value = {"sheets": []}
    spreadsheets.batchUpdate.return_value.execute.return_value = {
        "replies": [{"addSheet": {"properties": {"sheetId": 777}}}]
    }

    result = client.create_sheet("New Sheet")

    assert result == 777
    spreadsheets.batchUpdate.assert_called_once_with(
        spreadsheetId="spreadsheet-id",
        body={"requests": [{"addSheet": {"properties": {"title": "New Sheet"}}}]},
    )


def test_create_sheet_raises_for_duplicate_name() -> None:
    client, _, spreadsheets, _ = _build_client_with_service()
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Existing"}}]
    }

    with pytest.raises(SheetAlreadyExistsError, match="already exists"):
        client.create_sheet("Existing")

    spreadsheets.batchUpdate.assert_not_called()


def test_delete_sheet_deletes_existing_sheet() -> None:
    client, _, spreadsheets, _ = _build_client_with_service()
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Archive", "sheetId": 9001}}]
    }
    spreadsheets.batchUpdate.return_value.execute.return_value = {"replies": []}

    client.delete_sheet("Archive")

    spreadsheets.batchUpdate.assert_called_once_with(
        spreadsheetId="spreadsheet-id",
        body={"requests": [{"deleteSheet": {"sheetId": 9001}}]},
    )


def test_delete_sheet_raises_for_missing_sheet() -> None:
    client, _, spreadsheets, _ = _build_client_with_service()
    spreadsheets.get.return_value.execute.return_value = {"sheets": []}

    with pytest.raises(SheetNotFoundError, match="was not found"):
        client.delete_sheet("Missing")

    spreadsheets.batchUpdate.assert_not_called()


def test_write_range_uses_raw_input_mode() -> None:
    client, _, _, values = _build_client_with_service()
    values.update.return_value.execute.return_value = {"updatedCells": 2}

    result = client.write_range("Sheet1!A1:B1", [["=1+1", "+7 999 123-45-67"]])

    assert result == {"updatedCells": 2}
    values.update.assert_called_once_with(
        spreadsheetId="spreadsheet-id",
        range="Sheet1!A1:B1",
        valueInputOption="RAW",
        body={"values": [["=1+1", "+7 999 123-45-67"]]},
    )


def test_append_rows_appends_with_insert_rows_mode() -> None:
    client, _, _, values = _build_client_with_service()
    values.append.return_value.execute.return_value = {"updates": {"updatedRows": 2}}

    result = client.append_rows("Sheet1!A:B", [["A", "B"], ["C", "D"]])

    assert result == {"updates": {"updatedRows": 2}}
    values.append.assert_called_once_with(
        spreadsheetId="spreadsheet-id",
        range="Sheet1!A:B",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [["A", "B"], ["C", "D"]]},
    )


def test_clear_range_clears_requested_range() -> None:
    client, _, _, values = _build_client_with_service()
    values.clear.return_value.execute.return_value = {"clearedRange": "Sheet1!A1:B2"}

    result = client.clear_range("Sheet1!A1:B2")

    assert result == {"clearedRange": "Sheet1!A1:B2"}
    values.clear.assert_called_once_with(
        spreadsheetId="spreadsheet-id",
        range="Sheet1!A1:B2",
        body={},
    )


def test_format_range_sends_repeat_cell_request() -> None:
    client, _, spreadsheets, _ = _build_client_with_service()
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Format", "sheetId": 55}}]
    }
    spreadsheets.batchUpdate.return_value.execute.return_value = {"replies": []}

    client.format_range(
        "Format",
        0,
        1,
        0,
        3,
        background_color={"red": 1.0, "green": 0.9, "blue": 0.8},
        bold=True,
        font_size=12,
        horizontal_alignment="CENTER",
        vertical_alignment="MIDDLE",
        wrap_strategy="WRAP",
        number_format={"type": "NUMBER", "pattern": "0.00"},
    )

    spreadsheets.batchUpdate.assert_called_once_with(
        spreadsheetId="spreadsheet-id",
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": 55,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": 3,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {
                                    "red": 1.0,
                                    "green": 0.9,
                                    "blue": 0.8,
                                },
                                "textFormat": {"bold": True, "fontSize": 12},
                                "horizontalAlignment": "CENTER",
                                "verticalAlignment": "MIDDLE",
                                "wrapStrategy": "WRAP",
                                "numberFormat": {
                                    "type": "NUMBER",
                                    "pattern": "0.00",
                                },
                            }
                        },
                        "fields": (
                            "userEnteredFormat.backgroundColor,"
                            "userEnteredFormat.textFormat.bold,"
                            "userEnteredFormat.textFormat.fontSize,"
                            "userEnteredFormat.horizontalAlignment,"
                            "userEnteredFormat.verticalAlignment,"
                            "userEnteredFormat.wrapStrategy,"
                            "userEnteredFormat.numberFormat"
                        ),
                    }
                }
            ]
        },
    )


def test_merge_cells_sends_merge_request() -> None:
    client, _, spreadsheets, _ = _build_client_with_service()
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Merge", "sheetId": 88}}]
    }
    spreadsheets.batchUpdate.return_value.execute.return_value = {"replies": []}

    client.merge_cells("Merge", 1, 2, 0, 2)

    spreadsheets.batchUpdate.assert_called_once_with(
        spreadsheetId="spreadsheet-id",
        body={
            "requests": [
                {
                    "mergeCells": {
                        "range": {
                            "sheetId": 88,
                            "startRowIndex": 1,
                            "endRowIndex": 2,
                            "startColumnIndex": 0,
                            "endColumnIndex": 2,
                        },
                        "mergeType": "MERGE_ALL",
                    }
                }
            ]
        },
    )


def test_set_column_width_updates_dimension_properties() -> None:
    client, _, spreadsheets, _ = _build_client_with_service()
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Width", "sheetId": 44}}]
    }
    spreadsheets.batchUpdate.return_value.execute.return_value = {"replies": []}

    client.set_column_width("Width", 0, 3, 180)

    spreadsheets.batchUpdate.assert_called_once_with(
        spreadsheetId="spreadsheet-id",
        body={
            "requests": [
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": 44,
                            "dimension": "COLUMNS",
                            "startIndex": 0,
                            "endIndex": 3,
                        },
                        "properties": {"pixelSize": 180},
                        "fields": "pixelSize",
                    }
                }
            ]
        },
    )


def test_freeze_rows_updates_sheet_properties() -> None:
    client, _, spreadsheets, _ = _build_client_with_service()
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Frozen", "sheetId": 11}}]
    }
    spreadsheets.batchUpdate.return_value.execute.return_value = {"replies": []}

    client.freeze_rows("Frozen", 1)

    spreadsheets.batchUpdate.assert_called_once_with(
        spreadsheetId="spreadsheet-id",
        body={
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": 11,
                            "gridProperties": {"frozenRowCount": 1},
                        },
                        "fields": "gridProperties.frozenRowCount",
                    }
                }
            ]
        },
    )


def test_batch_write_ranges_sends_single_values_batch_update() -> None:
    client, _, _, values = _build_client_with_service()
    values.batchUpdate.return_value.execute.return_value = {"totalUpdatedCells": 4}

    result = client.batch_write_ranges(
        [
            ("Sheet1!A1", [["Title"]]),
            ("Sheet1!A3:B3", [["Label", "Value"]]),
        ]
    )

    assert result == {"totalUpdatedCells": 4}
    values.batchUpdate.assert_called_once_with(
        spreadsheetId="spreadsheet-id",
        body={
            "valueInputOption": "RAW",
            "data": [
                {"range": "Sheet1!A1", "values": [["Title"]]},
                {"range": "Sheet1!A3:B3", "values": [["Label", "Value"]]},
            ],
        },
    )


def test_batch_write_ranges_requires_at_least_one_entry() -> None:
    client, _, _, _ = _build_client_with_service()

    with pytest.raises(GoogleSheetsValidationError):
        client.batch_write_ranges([])


def test_batch_update_combines_multiple_requests_in_one_call() -> None:
    client, _, spreadsheets, _ = _build_client_with_service()
    spreadsheets.batchUpdate.return_value.execute.return_value = {"replies": []}
    sheet_id = 42

    requests = [
        client.build_merge_request(sheet_id, 0, 1, 0, 3),
        client.build_freeze_rows_request(sheet_id, 1),
    ]
    result = client.batch_update(requests)

    assert result == {"replies": []}
    spreadsheets.get.assert_not_called()
    spreadsheets.batchUpdate.assert_called_once_with(
        spreadsheetId="spreadsheet-id",
        body={"requests": requests},
    )


def test_batch_update_requires_at_least_one_request() -> None:
    client, _, _, _ = _build_client_with_service()

    with pytest.raises(GoogleSheetsValidationError):
        client.batch_update([])


def test_delete_sheet_by_id_skips_metadata_lookup() -> None:
    client, _, spreadsheets, _ = _build_client_with_service()
    spreadsheets.batchUpdate.return_value.execute.return_value = {"replies": []}

    client.delete_sheet_by_id(999)

    spreadsheets.get.assert_not_called()
    spreadsheets.batchUpdate.assert_called_once_with(
        spreadsheetId="spreadsheet-id",
        body={"requests": [{"deleteSheet": {"sheetId": 999}}]},
    )


def test_metadata_read_retries_on_429_then_succeeds() -> None:
    sleep_calls: list[float] = []
    client, _, spreadsheets, _ = _build_client_with_service(retry_sleep=sleep_calls.append)
    spreadsheets.get.return_value.execute.side_effect = [
        _http_error(429),
        {"sheets": [{"properties": {"title": "Summary"}}]},
    ]

    result = client.get_sheet_names()

    assert result == ["Summary"]
    assert spreadsheets.get.return_value.execute.call_count == 2
    assert sleep_calls == [0.5]


def test_write_range_retries_on_transient_5xx_then_succeeds() -> None:
    sleep_calls: list[float] = []
    client, _, _, values = _build_client_with_service(retry_sleep=sleep_calls.append)
    values.update.return_value.execute.side_effect = [
        _http_error(503),
        {"updatedCells": 2},
    ]

    result = client.write_range("Sheet1!A1:B1", [["a", "b"]])

    assert result == {"updatedCells": 2}
    assert values.update.return_value.execute.call_count == 2
    assert sleep_calls == [0.5]


def test_batch_update_retries_transient_5xx_then_succeeds() -> None:
    sleep_calls: list[float] = []
    client, _, spreadsheets, _ = _build_client_with_service(retry_sleep=sleep_calls.append)
    spreadsheets.batchUpdate.return_value.execute.side_effect = [
        _http_error(500),
        {"replies": []},
    ]

    result = client.batch_update([{"mergeCells": {}}])

    assert result == {"replies": []}
    assert spreadsheets.batchUpdate.return_value.execute.call_count == 2
    assert sleep_calls == [0.5]


def test_retryable_operation_stops_after_max_attempts() -> None:
    sleep_calls: list[float] = []
    client, _, spreadsheets, _ = _build_client_with_service(retry_sleep=sleep_calls.append)
    spreadsheets.get.return_value.execute.side_effect = [
        _http_error(429),
        _http_error(429),
        _http_error(429),
    ]

    with pytest.raises(GoogleSheetsAPIError, match="429"):
        client.get_sheet_names()

    # DEFAULT_MAX_RETRY_ATTEMPTS = 3: two retries after the first attempt.
    assert spreadsheets.get.return_value.execute.call_count == 3
    assert sleep_calls == [0.5, 1.0]


def test_non_retryable_status_is_not_retried() -> None:
    sleep_calls: list[float] = []
    client, _, spreadsheets, _ = _build_client_with_service(retry_sleep=sleep_calls.append)
    spreadsheets.get.return_value.execute.side_effect = _http_error(403)

    with pytest.raises(GoogleSheetsAPIError, match="403"):
        client.get_sheet_names()

    assert spreadsheets.get.return_value.execute.call_count == 1
    assert sleep_calls == []


def test_create_sheet_is_not_retried_on_retryable_status() -> None:
    """Worksheet creation must never be automatically retried, even on a
    status code that would be retryable for other operations, because a
    retry after an ambiguous failure could create a duplicate sheet.
    """
    sleep_calls: list[float] = []
    client, _, spreadsheets, _ = _build_client_with_service(retry_sleep=sleep_calls.append)
    spreadsheets.get.return_value.execute.return_value = {"sheets": []}
    spreadsheets.batchUpdate.return_value.execute.side_effect = _http_error(429)

    with pytest.raises(GoogleSheetsAPIError, match="429"):
        client.create_sheet("New Sheet")

    assert spreadsheets.batchUpdate.return_value.execute.call_count == 1
    assert sleep_calls == []


def test_delete_sheet_by_id_retries_on_transient_failure() -> None:
    sleep_calls: list[float] = []
    client, _, spreadsheets, _ = _build_client_with_service(retry_sleep=sleep_calls.append)
    spreadsheets.batchUpdate.return_value.execute.side_effect = [
        _http_error(503),
        {"replies": []},
    ]

    client.delete_sheet_by_id(123)

    assert spreadsheets.batchUpdate.return_value.execute.call_count == 2
    assert sleep_calls == [0.5]
