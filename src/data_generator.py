from __future__ import annotations

from datetime import timedelta
from random import Random

from src.models import (
    ALLOWED_DEAL_DIRECTIONS,
    ALLOWED_RISK_LEVELS,
    ALLOWED_STATUSES,
    CreditDeal,
    ReportParameters,
)


class CreditDealDataGenerator:
    """Deterministic simulator for fictional credit portfolio data."""

    PROJECT_NAMES = (
        "Aurora",
        "Atlas",
        "Beacon",
        "Cascade",
        "Drift",
        "Element",
        "Frontier",
        "Helix",
        "Northstar",
        "Summit",
    )
    LIMIT_RANGES = {
        "RUB": (450_000_000.0, 6_500_000_000.0),
        "USD": (6_000_000.0, 140_000_000.0),
        "EUR": (5_000_000.0, 120_000_000.0),
    }
    RATE_RANGES = {
        "RUB": (8.5, 15.5),
        "USD": (4.0, 9.0),
        "EUR": (3.0, 7.5),
    }
    DIRECTION_LIMIT_FACTORS = {
        "Project Finance": 1.15,
        "Corporate Finance": 1.0,
        "International Projects": 1.25,
    }
    STATUS_WEIGHTS = (0.55, 0.2, 0.15, 0.1)
    HIGH_RISK_WEIGHTS = {
        "Active": (0.45, 0.4, 0.15),
        "Monitoring": (0.2, 0.5, 0.3),
        "Restructuring": (0.1, 0.35, 0.55),
        "Closed": (0.6, 0.3, 0.1),
    }

    def generate(
        self, parameters: ReportParameters, seed: int | None = None
    ) -> list[CreditDeal]:
        rng = Random(seed)
        deals: list[CreditDeal] = []

        for index in range(1, parameters.records_count + 1):
            direction = self._pick_direction(parameters.direction, rng)
            review_date = self._pick_review_date(parameters, rng)
            maturity_date = review_date + timedelta(days=rng.randint(180, 2_400))
            status = rng.choices(ALLOWED_STATUSES, weights=self.STATUS_WEIGHTS, k=1)[0]
            risk_level = rng.choices(
                ALLOWED_RISK_LEVELS,
                weights=self.HIGH_RISK_WEIGHTS[status],
                k=1,
            )[0]
            approved_limit = self._generate_limit(
                parameters.reporting_currency,
                direction,
                rng,
            )
            outstanding_amount = self._generate_outstanding_amount(
                approved_limit,
                status,
                rng,
            )
            interest_rate = round(
                rng.uniform(*self.RATE_RANGES[parameters.reporting_currency]),
                2,
            )

            deals.append(
                CreditDeal(
                    deal_id=f"DL-{review_date.strftime('%Y%m')}-{index:04d}",
                    borrower=f"Borrower-{index:03d}",
                    project=f"Project {rng.choice(self.PROJECT_NAMES)}-{index:03d}",
                    direction=direction,
                    currency=parameters.reporting_currency,
                    approved_limit=approved_limit,
                    outstanding_amount=outstanding_amount,
                    interest_rate=interest_rate,
                    review_date=review_date,
                    maturity_date=maturity_date,
                    status=status,
                    risk_level=risk_level,
                )
            )

        return deals

    def _pick_direction(self, requested_direction: str, rng: Random) -> str:
        if requested_direction == "All":
            return rng.choice(ALLOWED_DEAL_DIRECTIONS)
        return requested_direction

    def _pick_review_date(self, parameters: ReportParameters, rng: Random):
        day_offset = rng.randint(0, (parameters.end_date - parameters.start_date).days)
        return parameters.start_date + timedelta(days=day_offset)

    def _generate_limit(self, currency: str, direction: str, rng: Random) -> float:
        min_value, max_value = self.LIMIT_RANGES[currency]
        factor = self.DIRECTION_LIMIT_FACTORS[direction]
        approved_limit = rng.uniform(min_value * factor, max_value * factor)
        return round(approved_limit, 2)

    def _generate_outstanding_amount(
        self, approved_limit: float, status: str, rng: Random
    ) -> float:
        if status == "Closed":
            return 0.0
        utilization = rng.uniform(0.2, 0.92)
        if status == "Restructuring":
            utilization = min(0.98, utilization + 0.08)
        return round(approved_limit * utilization, 2)
