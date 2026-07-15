from __future__ import annotations

from datetime import date

import pytest

from src.models import ReportParameters


def test_report_parameters_accept_valid_values() -> None:
    parameters = ReportParameters(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
        direction="Project Finance",
        reporting_currency="USD",
        records_count=25,
    )

    assert parameters.direction == "Project Finance"
    assert parameters.reporting_currency == "USD"


def test_report_parameters_reject_invalid_date_range() -> None:
    with pytest.raises(ValueError, match="start_date"):
        ReportParameters(
            start_date=date(2026, 7, 31),
            end_date=date(2026, 7, 1),
            direction="All",
            reporting_currency="USD",
            records_count=10,
        )


def test_report_parameters_reject_invalid_direction() -> None:
    with pytest.raises(ValueError, match="Unsupported direction"):
        ReportParameters(
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            direction="Retail Banking",
            reporting_currency="USD",
            records_count=10,
        )


def test_report_parameters_reject_invalid_currency() -> None:
    with pytest.raises(ValueError, match="Unsupported reporting currency"):
        ReportParameters(
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            direction="All",
            reporting_currency="GBP",
            records_count=10,
        )


def test_report_parameters_reject_records_count_out_of_range() -> None:
    with pytest.raises(ValueError, match="records_count"):
        ReportParameters(
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            direction="All",
            reporting_currency="USD",
            records_count=0,
        )
