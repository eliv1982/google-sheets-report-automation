from __future__ import annotations

from datetime import date

import pytest

from src.report_generator import (
    ReportFormError,
    build_report_parameters_from_form,
    parse_date_input,
    parse_form_data,
    parse_optional_seed,
)


def test_parse_date_input_accepts_valid_iso_date() -> None:
    assert parse_date_input("2026-07-15", "Start Date") == date(2026, 7, 15)


def test_parse_date_input_rejects_invalid_format() -> None:
    with pytest.raises(ReportFormError, match="YYYY-MM-DD"):
        parse_date_input("15/07/2026", "Start Date")


def test_build_report_parameters_rejects_invalid_date_order() -> None:
    with pytest.raises(ReportFormError, match="start_date"):
        build_report_parameters_from_form(
            start_date_value="2026-07-31",
            end_date_value="2026-07-01",
            direction="All",
            reporting_currency="USD",
            records_count_value="20",
        )


def test_build_report_parameters_rejects_invalid_records_count() -> None:
    with pytest.raises(ReportFormError, match="records_count"):
        build_report_parameters_from_form(
            start_date_value="2026-07-01",
            end_date_value="2026-07-31",
            direction="All",
            reporting_currency="USD",
            records_count_value="0",
        )


def test_parse_optional_seed_returns_none_for_empty_value() -> None:
    assert parse_optional_seed("   ") is None


def test_parse_optional_seed_returns_integer_for_valid_value() -> None:
    assert parse_optional_seed("42") == 42


def test_parse_optional_seed_rejects_invalid_value() -> None:
    with pytest.raises(ReportFormError, match="integer"):
        parse_optional_seed("abc")


def test_parse_form_data_builds_report_parameters() -> None:
    form_data = parse_form_data(
        start_date_value="2026-07-01",
        end_date_value="2026-07-31",
        direction="Project Finance",
        reporting_currency="EUR",
        records_count_value="25",
        random_seed_value="7",
    )

    assert form_data.parameters.start_date == date(2026, 7, 1)
    assert form_data.parameters.end_date == date(2026, 7, 31)
    assert form_data.parameters.direction == "Project Finance"
    assert form_data.parameters.reporting_currency == "EUR"
    assert form_data.parameters.records_count == 25
    assert form_data.random_seed == 7
