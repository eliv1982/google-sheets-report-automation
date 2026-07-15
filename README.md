# Google Sheets Report Automation

Desktop utility and supporting Python services for generating simulated management reports in Google Sheets.

## Purpose

This project was built as a homework-style automation exercise:

- connect safely to an existing Google Spreadsheet through a service account;
- read and write data without exposing secrets;
- simulate a fictional credit portfolio dataset;
- generate a formatted management report in a new sheet;
- provide a simple `tkinter` desktop UI for running the process manually.

All business data in the project is fully simulated and anonymized.

## Features

- Safe configuration loading from `.env`
- Google Sheets API access via official Python client
- Reusable `GoogleSheetsClient` for read, write, CRUD, and formatting operations
- Deterministic offline data generator for fictional credit portfolio deals
- Report service that creates a structured management report in a new Google Sheets tab
- Offline preview mode without any Google API calls
- Read and write smoke-test scripts
- `tkinter` desktop UI for manual report generation
- Offline unit tests with mocks

## Architecture

- `src/config.py` loads `.env`, validates `GOOGLE_APPLICATION_CREDENTIALS` and `GOOGLE_SPREADSHEET_ID`, and checks that the credentials file exists.
- `src/google_sheets.py` is the infrastructure layer for Google Sheets API operations.
- `src/models.py` contains typed report models such as `ReportParameters`, `CreditDeal`, and `ReportSummary`.
- `src/data_generator.py` generates deterministic fictional portfolio data for offline testing and demos.
- `src/report_styles.py` stores report-specific formatting constants and visual settings.
- `src/report_service.py` contains the business logic that prepares and writes the formatted management report.
- `src/report_generator.py` contains testable form parsing plus the `tkinter` UI.
- `scripts/` contains thin launchers and smoke/preview scripts.
- `tests/` contains offline unit tests.

## Project Requirements

- Python 3.12 or newer is recommended
- Access to Google Cloud with Google Sheets API enabled
- A service account with access to the target spreadsheet
- An existing Google Spreadsheet shared with that service account

`tkinter` is part of the Python standard library and is not installed through `pip`.

## Google Cloud and Google Sheets Setup

1. Create or select a Google Cloud project.
2. Enable the Google Sheets API for that project.
3. Create a service account.
4. Download the service account JSON key file.
5. Store the file locally as `credentials/service-account.json`.
6. Share the target Google Spreadsheet with the service account email and grant it Editor access.

Do not commit the JSON key file to the repository.

## Safe Local Configuration

1. Copy `.env.example` to `.env`.
2. Set:
   - `GOOGLE_APPLICATION_CREDENTIALS`
   - `GOOGLE_SPREADSHEET_ID`
3. Keep `.env` local only.

The repository is already configured so that `.env` and `credentials/` are not meant to be committed.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## Desktop UI

Run the report generator UI:

```powershell
.\.venv\Scripts\python .\scripts\run_report_generator.py
```

The form includes:

- `Start Date` in `YYYY-MM-DD`
- `End Date` in `YYYY-MM-DD`
- `Direction`
- `Reporting Currency`
- `Number of Deals`
- `Optional Random Seed`

Default values:

- Start Date: approximately 30 days ago
- End Date: today
- Direction: `All`
- Reporting Currency: `USD`
- Number of Deals: `20`

During generation the `Generate Report` button is temporarily disabled to prevent double submission.

## Generated Report Structure

Each report is created in a new sheet with a unique name such as `Report_20260715_163000`.

The Google Sheets report contains:

- merged title row: `CREDIT PORTFOLIO MANAGEMENT REPORT`
- reporting metadata:
  - reporting period
  - direction
  - reporting currency
  - generated at
- KPI block:
  - total deals
  - approved limit
  - outstanding amount
  - average interest rate
  - active deals
  - high risk deals
- detailed deal table
- risk overview section

Formatting includes:

- merged title
- calm professional colors
- bold section headers
- wrap text
- tuned column widths
- row heights
- limited header-area freeze to keep report metadata visible during scrolling
- number formats for money and percentage fields

## Simulated Data

The generator creates fictional and anonymized records only, for example:

- `Borrower-001`
- `Project Aurora-001`
- `DL-202607-0001`

No real personal data is used.

Currency figures are demonstration values only.
Real FX APIs are not used anywhere in this project.

## Commands

Read smoke-test:

```powershell
.\.venv\Scripts\python .\scripts\smoke_test_sheets.py
```

Write smoke-test:

```powershell
.\.venv\Scripts\python .\scripts\smoke_test_sheets_write.py
```

Offline preview:

```powershell
.\.venv\Scripts\python .\scripts\preview_report.py
```

Generate sample live report:

```powershell
.\.venv\Scripts\python .\scripts\generate_sample_report.py
```

Run tests:

```powershell
.\.venv\Scripts\python -m pytest
```

## Security Notes

- Never commit `.env`.
- Never commit `credentials/service-account.json`.
- Never hardcode Spreadsheet IDs or credential paths in source code.
- Do not log or print credential contents.
- Write operations should only target newly created report sheets or temporary smoke-test sheets.
- Read operations may access the configured spreadsheet without modifying existing user sheets.
- Existing user sheets must never be modified or deleted unintentionally.

## Future Improvements

- Connect to real corporate source systems or internal APIs
- Import source data from CSV/XLSX
- Schedule automatic report creation
- Add Google Drive API support for automatic spreadsheet creation
- Add real FX rates through a separate provider layer
- Add export and distribution workflows
- Add dashboards and charts
