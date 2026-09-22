from __future__ import annotations

import logging
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from src.models import CreditDeal, ReportParameters
from src.report_service import CreditPortfolioReportService


def _build_parameters() -> ReportParameters:
    return ReportParameters(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
        direction="All",
        reporting_currency="USD",
        records_count=3,
    )


def _build_deals() -> list[CreditDeal]:
    return [
        CreditDeal(
            deal_id="DL-202607-0001",
            borrower="Borrower-001",
            project="Project Aurora-001",
            direction="Project Finance",
            currency="USD",
            approved_limit=100.0,
            outstanding_amount=60.0,
            interest_rate=5.0,
            review_date=date(2026, 7, 2),
            maturity_date=date(2027, 7, 2),
            status="Active",
            risk_level="Low",
        ),
        CreditDeal(
            deal_id="DL-202607-0002",
            borrower="Borrower-002",
            project="Project Atlas-002",
            direction="Corporate Finance",
            currency="USD",
            approved_limit=200.0,
            outstanding_amount=150.0,
            interest_rate=7.0,
            review_date=date(2026, 7, 10),
            maturity_date=date(2027, 8, 10),
            status="Monitoring",
            risk_level="High",
        ),
        CreditDeal(
            deal_id="DL-202607-0003",
            borrower="Borrower-003",
            project="Project Summit-003",
            direction="International Projects",
            currency="USD",
            approved_limit=300.0,
            outstanding_amount=0.0,
            interest_rate=9.0,
            review_date=date(2026, 7, 18),
            maturity_date=date(2028, 1, 18),
            status="Closed",
            risk_level="Medium",
        ),
    ]


def _build_service(client: MagicMock) -> CreditPortfolioReportService:
    return CreditPortfolioReportService(
        client,
        _build_parameters(),
        _build_deals(),
        now_provider=lambda: datetime(2026, 7, 15, 16, 30, 0),
    )


def test_calculate_summary_returns_expected_kpis() -> None:
    summary = CreditPortfolioReportService.calculate_summary(_build_deals())

    assert summary.total_deals == 3
    assert summary.total_approved_limit == 600.0
    assert summary.total_outstanding == 210.0
    assert summary.average_interest_rate == 7.0
    assert summary.active_deals == 1
    assert summary.high_risk_deals == 1


def test_build_unique_sheet_name_appends_suffix_on_conflict() -> None:
    client = MagicMock()
    service = _build_service(client)

    sheet_name = service.build_unique_sheet_name(
        existing_names=["Report_20260715_163000"],
        generated_at=datetime(2026, 7, 15, 16, 30, 0),
    )

    assert sheet_name == "Report_20260715_163000_01"


def test_generate_report_calls_google_sheets_client_in_expected_sequence() -> None:
    client = MagicMock()
    client.get_sheet_names.return_value = ["Sheet1"]
    client.create_sheet.return_value = 555
    service = _build_service(client)

    created_sheet_name = service.generate_report()

    assert created_sheet_name == "Report_20260715_163000"
    client.create_sheet.assert_called_once_with("Report_20260715_163000")

    # Report values are written with a single combined values.batchUpdate call.
    client.batch_write_ranges.assert_called_once()
    entries = client.batch_write_ranges.call_args.args[0]
    assert len(entries) >= 5

    # Formatting/merge/dimension/freeze requests are combined into a single
    # spreadsheets.batchUpdate call, built against the known sheet id.
    client.build_merge_request.assert_any_call(555, 0, 1, 0, 12)
    client.build_merge_request.assert_any_call(555, 7, 8, 0, 6)
    client.build_freeze_rows_request.assert_called_once_with(555, 6)

    client.batch_update.assert_called_once()
    requests = client.batch_update.call_args.args[0]
    assert len(requests) >= 10


def test_write_report_produces_exact_ranges_for_known_deal_count() -> None:
    client = MagicMock()
    client.get_sheet_names.return_value = []
    client.create_sheet.return_value = 1
    service = _build_service(client)

    service.generate_report()

    sheet = "Report_20260715_163000"
    entries = dict(client.batch_write_ranges.call_args.args[0])

    assert f"'{sheet}'!A1" in entries
    assert entries[f"'{sheet}'!A1"] == [[CreditPortfolioReportService.TITLE]]
    # Header row: 12 detail columns -> column L.
    assert f"'{sheet}'!A13:L13" in entries
    # 3 deals -> detail rows 14-16.
    assert f"'{sheet}'!A14:L16" in entries
    # Risk title row = DETAIL_HEADER_ROW(13) + deal_count(3) + 2 = 18.
    assert f"'{sheet}'!A18" in entries
    assert f"'{sheet}'!A19:B21" in entries


def test_generate_report_reuses_sheet_id_without_extra_lookup() -> None:
    client = MagicMock()
    client.get_sheet_names.return_value = ["Sheet1"]
    client.create_sheet.return_value = 777
    service = _build_service(client)

    service.generate_report()

    client.get_sheet_id.assert_not_called()
    client.format_range.assert_not_called()
    client.merge_cells.assert_not_called()
    client.set_row_height.assert_not_called()
    client.set_column_width.assert_not_called()
    client.freeze_rows.assert_not_called()
    client.write_range.assert_not_called()


def test_generate_report_never_modifies_or_deletes_sheet1() -> None:
    client = MagicMock()
    client.get_sheet_names.return_value = ["Sheet1"]
    client.create_sheet.return_value = 42
    service = _build_service(client)

    service.generate_report()

    assert client.create_sheet.call_args.args[0] != "Sheet1"
    entries = client.batch_write_ranges.call_args.args[0]
    assert all("Sheet1" not in range_name for range_name, _ in entries)
    client.delete_sheet.assert_not_called()
    client.delete_sheet_by_id.assert_not_called()


def test_generate_report_cleans_up_by_sheet_id_when_write_fails() -> None:
    client = MagicMock()
    client.get_sheet_names.return_value = ["Sheet1"]
    client.create_sheet.return_value = 88
    client.batch_write_ranges.side_effect = RuntimeError("write failed")
    service = _build_service(client)

    with pytest.raises(RuntimeError, match="write failed"):
        service.generate_report()

    client.create_sheet.assert_called_once_with("Report_20260715_163000")
    client.delete_sheet_by_id.assert_called_once_with(88)


def test_generate_report_applies_formatting_and_safe_cleanup_on_failure() -> None:
    client = MagicMock()
    client.get_sheet_names.return_value = ["Sheet1"]
    client.create_sheet.return_value = 99
    client.batch_update.side_effect = RuntimeError("formatting failed")
    service = _build_service(client)

    with pytest.raises(RuntimeError, match="formatting failed"):
        service.generate_report()

    client.create_sheet.assert_called_once_with("Report_20260715_163000")
    client.delete_sheet_by_id.assert_called_once_with(99)


def test_generate_report_preserves_original_failure_when_cleanup_also_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = MagicMock()
    client.get_sheet_names.return_value = ["Sheet1"]
    client.create_sheet.return_value = 100
    client.batch_update.side_effect = RuntimeError("formatting failed")
    client.delete_sheet_by_id.side_effect = RuntimeError("cleanup failed")
    service = _build_service(client)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError) as excinfo:
            service.generate_report()

    # The original failure must be preserved as the raised exception, not
    # silently replaced by the cleanup failure.
    assert "formatting failed" in str(excinfo.value)
    assert "cleanup failed" not in str(excinfo.value)

    # The cleanup failure must still be surfaced clearly, not swallowed.
    assert any(
        "Cleanup failed" in record.message and "cleanup failed" in record.message.lower()
        for record in caplog.records
    )
    client.delete_sheet_by_id.assert_called_once_with(100)
