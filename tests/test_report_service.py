from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

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
    service = CreditPortfolioReportService(
        client,
        _build_parameters(),
        _build_deals(),
        now_provider=lambda: datetime(2026, 7, 15, 16, 30, 0),
    )

    sheet_name = service.build_unique_sheet_name(
        existing_names=["Report_20260715_163000"],
        generated_at=datetime(2026, 7, 15, 16, 30, 0),
    )

    assert sheet_name == "Report_20260715_163000_01"


def test_generate_report_calls_google_sheets_client_in_expected_sequence() -> None:
    client = MagicMock()
    client.get_sheet_names.return_value = ["Sheet1"]
    service = CreditPortfolioReportService(
        client,
        _build_parameters(),
        _build_deals(),
        now_provider=lambda: datetime(2026, 7, 15, 16, 30, 0),
    )

    created_sheet_name = service.generate_report()

    assert created_sheet_name == "Report_20260715_163000"
    client.create_sheet.assert_called_once_with("Report_20260715_163000")
    assert client.write_range.call_count >= 5
    client.merge_cells.assert_any_call("Report_20260715_163000", 0, 1, 0, 12)
    client.merge_cells.assert_any_call("Report_20260715_163000", 7, 8, 0, 6)
    client.freeze_rows.assert_called_once_with("Report_20260715_163000", 6)
    assert client.format_range.call_count >= 10


def test_generate_report_never_modifies_or_deletes_sheet1() -> None:
    client = MagicMock()
    client.get_sheet_names.return_value = ["Sheet1"]
    service = CreditPortfolioReportService(
        client,
        _build_parameters(),
        _build_deals(),
        now_provider=lambda: datetime(2026, 7, 15, 16, 30, 0),
    )

    service.generate_report()

    assert client.create_sheet.call_args.args[0] != "Sheet1"
    assert all("Sheet1" not in call.args[0] for call in client.write_range.call_args_list)
    client.delete_sheet.assert_not_called()


def test_generate_report_applies_formatting_and_safe_cleanup_on_failure() -> None:
    client = MagicMock()
    client.get_sheet_names.return_value = ["Sheet1"]
    client.format_range.side_effect = [None, RuntimeError("formatting failed")]
    service = CreditPortfolioReportService(
        client,
        _build_parameters(),
        _build_deals(),
        now_provider=lambda: datetime(2026, 7, 15, 16, 30, 0),
    )

    try:
        service.generate_report()
    except RuntimeError as error:
        assert "formatting failed" in str(error)
    else:
        raise AssertionError("Expected RuntimeError was not raised.")

    client.create_sheet.assert_called_once_with("Report_20260715_163000")
    client.delete_sheet.assert_called_once_with("Report_20260715_163000")
