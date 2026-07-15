from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config
from src.data_generator import CreditDealDataGenerator
from src.google_sheets import GoogleSheetsClient
from src.models import ReportParameters
from src.report_service import CreditPortfolioReportService


def main() -> int:
    config = load_config()
    client = GoogleSheetsClient.from_config(config)
    parameters = ReportParameters(
        start_date=date.today() - timedelta(days=30),
        end_date=date.today(),
        direction="All",
        reporting_currency="USD",
        records_count=20,
    )
    deals = CreditDealDataGenerator().generate(parameters, seed=42)
    report_service = CreditPortfolioReportService(client, parameters, deals)
    sheet_name = report_service.generate_report()

    print(f"Created report sheet: {sheet_name}")
    print("Sample management report generated successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
