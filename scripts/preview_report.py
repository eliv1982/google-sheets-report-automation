from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_generator import CreditDealDataGenerator
from src.models import ReportParameters
from src.report_service import CreditPortfolioReportService


def main() -> int:
    parameters = ReportParameters(
        start_date=date.today() - timedelta(days=30),
        end_date=date.today(),
        direction="All",
        reporting_currency="USD",
        records_count=12,
    )
    generator = CreditDealDataGenerator()
    deals = generator.generate(parameters, seed=42)
    summary = CreditPortfolioReportService.calculate_summary(deals)

    print("Report Preview")
    print("--------------")
    print(f"Period: {parameters.start_date} to {parameters.end_date}")
    print(f"Direction: {parameters.direction}")
    print(f"Reporting Currency: {parameters.reporting_currency}")
    print(f"Records Count: {parameters.records_count}")
    print()
    print("KPI")
    print(f"Total Deals: {summary.total_deals}")
    print(f"Approved Limit: {summary.total_approved_limit:.2f}")
    print(f"Outstanding Amount: {summary.total_outstanding:.2f}")
    print(f"Average Interest Rate: {summary.average_interest_rate:.2f}%")
    print(f"Active Deals: {summary.active_deals}")
    print(f"High Risk Deals: {summary.high_risk_deals}")
    print()
    print("First 5 Deals")
    for deal in deals[:5]:
        print(
            f"{deal.deal_id} | {deal.borrower} | {deal.project} | "
            f"{deal.direction} | {deal.currency} | {deal.outstanding_amount:.2f} | "
            f"{deal.status} | {deal.risk_level}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
