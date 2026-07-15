from __future__ import annotations

from datetime import date

from src.data_generator import CreditDealDataGenerator
from src.models import ReportParameters


def test_data_generator_is_deterministic_with_seed() -> None:
    parameters = ReportParameters(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        direction="All",
        reporting_currency="EUR",
        records_count=8,
    )
    generator = CreditDealDataGenerator()

    first_run = generator.generate(parameters, seed=7)
    second_run = generator.generate(parameters, seed=7)

    assert first_run == second_run


def test_data_generator_respects_direction_filter() -> None:
    parameters = ReportParameters(
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
        direction="Corporate Finance",
        reporting_currency="USD",
        records_count=12,
    )

    deals = CreditDealDataGenerator().generate(parameters, seed=11)

    assert len(deals) == 12
    assert all(deal.direction == "Corporate Finance" for deal in deals)
    assert all(parameters.start_date <= deal.review_date <= parameters.end_date for deal in deals)
