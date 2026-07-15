from __future__ import annotations

from datetime import datetime
from typing import Callable, Sequence

from src.google_sheets import GoogleSheetsClient
from src.models import CreditDeal, ReportParameters, ReportSummary
from src import report_styles


class CreditPortfolioReportService:
    SHEET_PREFIX = "Report"
    DETAIL_HEADERS = (
        "Deal ID",
        "Borrower",
        "Project",
        "Direction",
        "Currency",
        "Approved Limit",
        "Outstanding Amount",
        "Interest Rate",
        "Review Date",
        "Maturity Date",
        "Status",
        "Risk Level",
    )
    TITLE = "CREDIT PORTFOLIO MANAGEMENT REPORT"
    DETAIL_HEADER_ROW = 13  # One-based row number.

    def __init__(
        self,
        client: GoogleSheetsClient,
        parameters: ReportParameters,
        deals: Sequence[CreditDeal],
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.client = client
        self.parameters = parameters
        self.deals = list(deals)
        self._now_provider = now_provider or datetime.now

    @staticmethod
    def calculate_summary(deals: Sequence[CreditDeal]) -> ReportSummary:
        total_deals = len(deals)
        total_approved_limit = round(sum(deal.approved_limit for deal in deals), 2)
        total_outstanding = round(sum(deal.outstanding_amount for deal in deals), 2)
        average_interest_rate = round(
            sum(deal.interest_rate for deal in deals) / total_deals,
            2,
        ) if total_deals else 0.0

        return ReportSummary(
            total_deals=total_deals,
            total_approved_limit=total_approved_limit,
            total_outstanding=total_outstanding,
            average_interest_rate=average_interest_rate,
            active_deals=sum(1 for deal in deals if deal.status == "Active"),
            monitoring_deals=sum(1 for deal in deals if deal.status == "Monitoring"),
            restructuring_deals=sum(
                1 for deal in deals if deal.status == "Restructuring"
            ),
            closed_deals=sum(1 for deal in deals if deal.status == "Closed"),
            low_risk_deals=sum(1 for deal in deals if deal.risk_level == "Low"),
            medium_risk_deals=sum(1 for deal in deals if deal.risk_level == "Medium"),
            high_risk_deals=sum(1 for deal in deals if deal.risk_level == "High"),
        )

    def build_unique_sheet_name(
        self,
        existing_names: Sequence[str] | None = None,
        generated_at: datetime | None = None,
    ) -> str:
        effective_generated_at = self._normalize_datetime(
            generated_at or self._now_provider()
        )
        base_name = f"{self.SHEET_PREFIX}_{effective_generated_at:%Y%m%d_%H%M%S}"
        known_names = set(
            existing_names if existing_names is not None else self.client.get_sheet_names()
        )

        if base_name not in known_names:
            return base_name

        suffix = 1
        while True:
            candidate = f"{base_name}_{suffix:02d}"
            if candidate not in known_names:
                return candidate
            suffix += 1

    def generate_report(self) -> str:
        generated_at = self._normalize_datetime(self._now_provider())
        summary = self.calculate_summary(self.deals)
        sheet_name = self.build_unique_sheet_name(generated_at=generated_at)
        created_sheet = False

        try:
            self.client.create_sheet(sheet_name)
            created_sheet = True
            self._write_report(sheet_name, summary, generated_at)
            self._apply_formatting(sheet_name, len(self.deals))
            return sheet_name
        except Exception:
            if created_sheet:
                self._cleanup_created_sheet(sheet_name)
            raise

    def _write_report(
        self,
        sheet_name: str,
        summary: ReportSummary,
        generated_at: datetime,
    ) -> None:
        last_column_letter = self._column_letter(len(self.DETAIL_HEADERS))
        self.client.write_range(
            self._sheet_range(sheet_name, "A1"),
            [[self.TITLE]],
        )
        self.client.merge_cells(sheet_name, 0, 1, 0, len(self.DETAIL_HEADERS))

        metadata_rows = [
            [
                "Reporting Period",
                f"{self.parameters.start_date.isoformat()} to {self.parameters.end_date.isoformat()}",
            ],
            ["Direction", self.parameters.direction],
            ["Reporting Currency", self.parameters.reporting_currency],
            ["Generated At", generated_at.strftime("%Y-%m-%d %H:%M:%S")],
        ]
        self.client.write_range(
            self._sheet_range(sheet_name, "A3:B6"),
            metadata_rows,
        )

        self.client.write_range(
            self._sheet_range(sheet_name, "A8"),
            [["KEY METRICS"]],
        )
        self.client.merge_cells(sheet_name, 7, 8, 0, 6)
        self.client.write_range(
            self._sheet_range(sheet_name, "A9:F11"),
            [
                [
                    "Total Deals",
                    summary.total_deals,
                    "Approved Limit",
                    summary.total_approved_limit,
                    "Outstanding Amount",
                    summary.total_outstanding,
                ],
                [
                    "Average Interest Rate",
                    summary.average_interest_rate,
                    "Active Deals",
                    summary.active_deals,
                    "High Risk Deals",
                    summary.high_risk_deals,
                ],
                [
                    "Closed Deals",
                    summary.closed_deals,
                    "Low Risk Deals",
                    summary.low_risk_deals,
                    "Medium Risk Deals",
                    summary.medium_risk_deals,
                ],
            ],
        )

        self.client.write_range(
            self._sheet_range(
                sheet_name,
                f"A{self.DETAIL_HEADER_ROW}:{last_column_letter}{self.DETAIL_HEADER_ROW}",
            ),
            [list(self.DETAIL_HEADERS)],
        )
        if self.deals:
            detail_start_row = self.DETAIL_HEADER_ROW + 1
            detail_end_row = detail_start_row + len(self.deals) - 1
            self.client.write_range(
                self._sheet_range(
                    sheet_name,
                    f"A{detail_start_row}:{last_column_letter}{detail_end_row}",
                ),
                [self._deal_to_row(deal) for deal in self.deals],
            )

        risk_title_row = self.DETAIL_HEADER_ROW + len(self.deals) + 2
        self.client.write_range(
            self._sheet_range(sheet_name, f"A{risk_title_row}"),
            [["Risk Overview"]],
        )
        self.client.merge_cells(sheet_name, risk_title_row - 1, risk_title_row, 0, 4)
        self.client.write_range(
            self._sheet_range(sheet_name, f"A{risk_title_row + 1}:B{risk_title_row + 3}"),
            [
                ["Low", summary.low_risk_deals],
                ["Medium", summary.medium_risk_deals],
                ["High", summary.high_risk_deals],
            ],
        )

    def _apply_formatting(self, sheet_name: str, deal_count: int) -> None:
        detail_row_start = self.DETAIL_HEADER_ROW
        detail_row_end = detail_row_start + deal_count
        risk_title_row = self.DETAIL_HEADER_ROW + deal_count + 2

        self.client.format_range(
            sheet_name,
            0,
            1,
            0,
            len(self.DETAIL_HEADERS),
            **report_styles.TITLE_CELL_FORMAT,
        )
        self.client.set_row_height(sheet_name, 0, 1, report_styles.TITLE_ROW_HEIGHT)

        self.client.format_range(sheet_name, 2, 6, 0, 1, **report_styles.LABEL_FORMAT)
        self.client.format_range(sheet_name, 2, 6, 1, 2, **report_styles.BODY_FORMAT)

        self.client.format_range(sheet_name, 7, 8, 0, 6, **report_styles.SECTION_TITLE_FORMAT)
        self.client.set_row_height(sheet_name, 7, 8, report_styles.SECTION_ROW_HEIGHT)
        self.client.format_range(sheet_name, 8, 11, 0, 6, **report_styles.BODY_FORMAT)
        self.client.format_range(sheet_name, 8, 11, 0, 1, **report_styles.LABEL_FORMAT)
        self.client.format_range(sheet_name, 8, 11, 2, 3, **report_styles.LABEL_FORMAT)
        self.client.format_range(sheet_name, 8, 11, 4, 5, **report_styles.LABEL_FORMAT)
        self.client.format_range(
            sheet_name,
            8,
            9,
            3,
            4,
            number_format=report_styles.MONEY_NUMBER_FORMAT,
        )
        self.client.format_range(
            sheet_name,
            8,
            9,
            5,
            6,
            number_format=report_styles.MONEY_NUMBER_FORMAT,
        )
        self.client.format_range(
            sheet_name,
            9,
            10,
            1,
            2,
            number_format=report_styles.PERCENT_NUMBER_FORMAT,
        )

        self.client.format_range(
            sheet_name,
            self.DETAIL_HEADER_ROW - 1,
            self.DETAIL_HEADER_ROW,
            0,
            len(self.DETAIL_HEADERS),
            **report_styles.TABLE_HEADER_FORMAT,
        )
        self.client.set_row_height(
            sheet_name,
            self.DETAIL_HEADER_ROW - 1,
            self.DETAIL_HEADER_ROW,
            report_styles.DETAIL_HEADER_ROW_HEIGHT,
        )
        self.client.freeze_rows(sheet_name, report_styles.FROZEN_TOP_ROWS)

        if deal_count:
            self.client.format_range(
                sheet_name,
                detail_row_start,
                detail_row_end,
                0,
                len(self.DETAIL_HEADERS),
                **report_styles.BODY_FORMAT,
            )
            self.client.format_range(
                sheet_name,
                detail_row_start,
                detail_row_end,
                3,
                5,
                **report_styles.CENTERED_BODY_FORMAT,
            )
            self.client.format_range(
                sheet_name,
                detail_row_start,
                detail_row_end,
                8,
                12,
                **report_styles.CENTERED_BODY_FORMAT,
            )
            self.client.format_range(
                sheet_name,
                detail_row_start,
                detail_row_end,
                5,
                7,
                number_format=report_styles.MONEY_NUMBER_FORMAT,
            )
            self.client.format_range(
                sheet_name,
                detail_row_start,
                detail_row_end,
                7,
                8,
                number_format=report_styles.PERCENT_NUMBER_FORMAT,
            )
            self.client.set_row_height(
                sheet_name,
                detail_row_start,
                detail_row_end,
                report_styles.DETAIL_ROW_HEIGHT,
            )

        self.client.format_range(
            sheet_name,
            risk_title_row - 1,
            risk_title_row,
            0,
            4,
            **report_styles.SECTION_TITLE_FORMAT,
        )
        self.client.set_row_height(
            sheet_name,
            risk_title_row - 1,
            risk_title_row,
            report_styles.SECTION_ROW_HEIGHT,
        )
        self.client.format_range(
            sheet_name,
            risk_title_row,
            risk_title_row + 3,
            0,
            2,
            **report_styles.BODY_FORMAT,
        )
        self.client.format_range(
            sheet_name,
            risk_title_row,
            risk_title_row + 3,
            0,
            1,
            **report_styles.LABEL_FORMAT,
        )

        for column_index, width_pixels in enumerate(report_styles.COLUMN_WIDTHS):
            self.client.set_column_width(
                sheet_name,
                column_index,
                column_index + 1,
                width_pixels,
            )

    def _cleanup_created_sheet(self, sheet_name: str) -> None:
        if sheet_name == "Sheet1":
            return
        if not sheet_name.startswith(f"{self.SHEET_PREFIX}_"):
            return
        self.client.delete_sheet(sheet_name)

    def _deal_to_row(self, deal: CreditDeal) -> list[object]:
        return [
            deal.deal_id,
            deal.borrower,
            deal.project,
            deal.direction,
            deal.currency,
            round(deal.approved_limit, 2),
            round(deal.outstanding_amount, 2),
            round(deal.interest_rate, 2),
            deal.review_date.isoformat(),
            deal.maturity_date.isoformat(),
            deal.status,
            deal.risk_level,
        ]

    def _sheet_range(self, sheet_name: str, range_reference: str) -> str:
        escaped_name = sheet_name.replace("'", "''")
        return f"'{escaped_name}'!{range_reference}"

    @staticmethod
    def _column_letter(column_number: int) -> str:
        result = ""
        current = column_number
        while current > 0:
            current, remainder = divmod(current - 1, 26)
            result = chr(65 + remainder) + result
        return result

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.replace(tzinfo=None)
