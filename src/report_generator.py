from __future__ import annotations

import traceback
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from tkinter import messagebox, ttk

from src.config import ConfigError, load_config
from src.data_generator import CreditDealDataGenerator
from src.google_sheets import GoogleSheetsClient, GoogleSheetsError
from src.models import (
    ALLOWED_DIRECTIONS,
    ALLOWED_REPORTING_CURRENCIES,
    MAX_RECORDS_COUNT,
    MIN_RECORDS_COUNT,
    ReportParameters,
)
from src.report_service import CreditPortfolioReportService


DATE_INPUT_FORMAT = "%Y-%m-%d"


class ReportFormError(ValueError):
    """Raised when the report generator form contains invalid user input."""


@dataclass(frozen=True)
class ParsedReportFormData:
    parameters: ReportParameters
    random_seed: int | None


def parse_date_input(value: str, field_name: str) -> date:
    try:
        return datetime.strptime(value.strip(), DATE_INPUT_FORMAT).date()
    except ValueError as error:
        raise ReportFormError(
            f"{field_name} must be in YYYY-MM-DD format."
        ) from error


def parse_records_count(value: str) -> int:
    normalized_value = value.strip()
    if not normalized_value:
        raise ReportFormError("Number of Deals is required.")

    try:
        return int(normalized_value)
    except ValueError as error:
        raise ReportFormError("Number of Deals must be an integer.") from error


def parse_optional_seed(value: str) -> int | None:
    normalized_value = value.strip()
    if not normalized_value:
        return None

    try:
        return int(normalized_value)
    except ValueError as error:
        raise ReportFormError("Optional Random Seed must be an integer.") from error


def build_report_parameters_from_form(
    start_date_value: str,
    end_date_value: str,
    direction: str,
    reporting_currency: str,
    records_count_value: str,
) -> ReportParameters:
    start_date = parse_date_input(start_date_value, "Start Date")
    end_date = parse_date_input(end_date_value, "End Date")
    records_count = parse_records_count(records_count_value)

    try:
        return ReportParameters(
            start_date=start_date,
            end_date=end_date,
            direction=direction,
            reporting_currency=reporting_currency,
            records_count=records_count,
        )
    except ValueError as error:
        raise ReportFormError(str(error)) from error


def parse_form_data(
    start_date_value: str,
    end_date_value: str,
    direction: str,
    reporting_currency: str,
    records_count_value: str,
    random_seed_value: str,
) -> ParsedReportFormData:
    parameters = build_report_parameters_from_form(
        start_date_value=start_date_value,
        end_date_value=end_date_value,
        direction=direction,
        reporting_currency=reporting_currency,
        records_count_value=records_count_value,
    )
    random_seed = parse_optional_seed(random_seed_value)
    return ParsedReportFormData(parameters=parameters, random_seed=random_seed)


def default_form_values() -> dict[str, str]:
    today = date.today()
    return {
        "start_date": (today - timedelta(days=30)).isoformat(),
        "end_date": today.isoformat(),
        "direction": "All",
        "reporting_currency": "USD",
        "records_count": "20",
        "random_seed": "",
    }


class ReportGeneratorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Google Sheets Report Generator")
        self.root.geometry("560x320")
        self.root.minsize(560, 320)

        defaults = default_form_values()
        self.start_date_var = tk.StringVar(value=defaults["start_date"])
        self.end_date_var = tk.StringVar(value=defaults["end_date"])
        self.direction_var = tk.StringVar(value=defaults["direction"])
        self.reporting_currency_var = tk.StringVar(
            value=defaults["reporting_currency"]
        )
        self.records_count_var = tk.StringVar(value=defaults["records_count"])
        self.random_seed_var = tk.StringVar(value=defaults["random_seed"])

        self.generate_button: ttk.Button | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.root, padding=18)
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main_frame.columnconfigure(1, weight=1)

        ttk.Label(
            main_frame,
            text="Generate a simulated management report in Google Sheets.",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        self._add_labeled_entry(main_frame, "Start Date", self.start_date_var, 1)
        self._add_labeled_entry(main_frame, "End Date", self.end_date_var, 2)
        self._add_labeled_combobox(
            main_frame,
            "Direction",
            self.direction_var,
            ALLOWED_DIRECTIONS,
            3,
        )
        self._add_labeled_combobox(
            main_frame,
            "Reporting Currency",
            self.reporting_currency_var,
            ALLOWED_REPORTING_CURRENCIES,
            4,
        )
        self._add_labeled_entry(
            main_frame,
            f"Number of Deals ({MIN_RECORDS_COUNT}-{MAX_RECORDS_COUNT})",
            self.records_count_var,
            5,
        )
        self._add_labeled_entry(
            main_frame,
            "Optional Random Seed",
            self.random_seed_var,
            6,
        )

        self.generate_button = ttk.Button(
            main_frame,
            text="Generate Report",
            command=self._on_generate_clicked,
        )
        self.generate_button.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(16, 0))

    def _add_labeled_entry(
        self,
        container: ttk.Frame,
        label_text: str,
        variable: tk.StringVar,
        row_index: int,
    ) -> None:
        ttk.Label(container, text=label_text).grid(
            row=row_index,
            column=0,
            sticky="w",
            pady=6,
            padx=(0, 12),
        )
        ttk.Entry(container, textvariable=variable).grid(
            row=row_index,
            column=1,
            sticky="ew",
            pady=6,
        )

    def _add_labeled_combobox(
        self,
        container: ttk.Frame,
        label_text: str,
        variable: tk.StringVar,
        values: tuple[str, ...],
        row_index: int,
    ) -> None:
        ttk.Label(container, text=label_text).grid(
            row=row_index,
            column=0,
            sticky="w",
            pady=6,
            padx=(0, 12),
        )
        ttk.Combobox(
            container,
            textvariable=variable,
            values=values,
            state="readonly",
        ).grid(
            row=row_index,
            column=1,
            sticky="ew",
            pady=6,
        )

    def _set_busy(self, is_busy: bool) -> None:
        if self.generate_button is not None:
            self.generate_button.configure(
                state=tk.DISABLED if is_busy else tk.NORMAL
            )
        self.root.update_idletasks()

    def _on_generate_clicked(self) -> None:
        self._set_busy(True)
        try:
            form_data = parse_form_data(
                start_date_value=self.start_date_var.get(),
                end_date_value=self.end_date_var.get(),
                direction=self.direction_var.get(),
                reporting_currency=self.reporting_currency_var.get(),
                records_count_value=self.records_count_var.get(),
                random_seed_value=self.random_seed_var.get(),
            )
            config = load_config()
            client = GoogleSheetsClient.from_config(config)
            deals = CreditDealDataGenerator().generate(
                form_data.parameters,
                seed=form_data.random_seed,
            )
            report_service = CreditPortfolioReportService(
                client=client,
                parameters=form_data.parameters,
                deals=deals,
            )
            sheet_name = report_service.generate_report()

            messagebox.showinfo(
                "Report Created",
                (
                    f"Report sheet: {sheet_name}\n"
                    f"Simulated deals: {form_data.parameters.records_count}\n"
                    "Management report generated successfully."
                ),
            )
        except (ReportFormError, ConfigError, GoogleSheetsError) as error:
            messagebox.showerror("Generation Error", str(error))
        except Exception:
            traceback.print_exc()
            messagebox.showerror(
                "Generation Error",
                "Unexpected error during report generation. Check the console log for details.",
            )
        finally:
            self._set_busy(False)


def main() -> int:
    root = tk.Tk()
    ReportGeneratorApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
