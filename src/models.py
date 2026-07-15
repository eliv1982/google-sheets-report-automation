from __future__ import annotations

from dataclasses import dataclass
from datetime import date


ALLOWED_DIRECTIONS = (
    "Project Finance",
    "Corporate Finance",
    "International Projects",
    "All",
)
ALLOWED_DEAL_DIRECTIONS = tuple(
    direction for direction in ALLOWED_DIRECTIONS if direction != "All"
)
ALLOWED_REPORTING_CURRENCIES = ("RUB", "USD", "EUR")
ALLOWED_STATUSES = ("Active", "Monitoring", "Restructuring", "Closed")
ALLOWED_RISK_LEVELS = ("Low", "Medium", "High")
MIN_RECORDS_COUNT = 1
MAX_RECORDS_COUNT = 500


@dataclass(frozen=True)
class ReportParameters:
    start_date: date
    end_date: date
    direction: str
    reporting_currency: str
    records_count: int

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("start_date must be earlier than or equal to end_date.")
        if self.direction not in ALLOWED_DIRECTIONS:
            raise ValueError(f"Unsupported direction: {self.direction}.")
        if self.reporting_currency not in ALLOWED_REPORTING_CURRENCIES:
            raise ValueError(
                f"Unsupported reporting currency: {self.reporting_currency}."
            )
        if not (MIN_RECORDS_COUNT <= self.records_count <= MAX_RECORDS_COUNT):
            raise ValueError(
                "records_count must be between "
                f"{MIN_RECORDS_COUNT} and {MAX_RECORDS_COUNT}."
            )


@dataclass(frozen=True)
class CreditDeal:
    deal_id: str
    borrower: str
    project: str
    direction: str
    currency: str
    approved_limit: float
    outstanding_amount: float
    interest_rate: float
    review_date: date
    maturity_date: date
    status: str
    risk_level: str

    def __post_init__(self) -> None:
        if self.direction not in ALLOWED_DEAL_DIRECTIONS:
            raise ValueError(f"Unsupported deal direction: {self.direction}.")
        if self.currency not in ALLOWED_REPORTING_CURRENCIES:
            raise ValueError(f"Unsupported deal currency: {self.currency}.")
        if self.status not in ALLOWED_STATUSES:
            raise ValueError(f"Unsupported status: {self.status}.")
        if self.risk_level not in ALLOWED_RISK_LEVELS:
            raise ValueError(f"Unsupported risk level: {self.risk_level}.")
        if self.approved_limit < 0 or self.outstanding_amount < 0:
            raise ValueError("Deal amounts must be non-negative.")
        if self.outstanding_amount > self.approved_limit:
            raise ValueError("Outstanding amount must not exceed approved limit.")
        if self.review_date > self.maturity_date:
            raise ValueError("review_date must not be later than maturity_date.")
        if self.interest_rate < 0:
            raise ValueError("interest_rate must be non-negative.")


@dataclass(frozen=True)
class ReportSummary:
    total_deals: int
    total_approved_limit: float
    total_outstanding: float
    average_interest_rate: float
    active_deals: int
    monitoring_deals: int
    restructuring_deals: int
    closed_deals: int
    low_risk_deals: int
    medium_risk_deals: int
    high_risk_deals: int
