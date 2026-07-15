from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(ValueError):
    """Raised when required application configuration is missing or invalid."""


@dataclass(frozen=True)
class AppConfig:
    credentials_path: Path
    spreadsheet_id: str


def load_config(env_file: Path | None = None) -> AppConfig:
    project_root = Path(__file__).resolve().parents[1]
    dotenv_path = env_file or project_root / ".env"

    load_dotenv(dotenv_path=dotenv_path, override=False)

    raw_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not raw_credentials_path:
        raise ConfigError(
            "Required environment variable GOOGLE_APPLICATION_CREDENTIALS is not set."
        )

    spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID", "").strip()
    if not spreadsheet_id:
        raise ConfigError(
            "Required environment variable GOOGLE_SPREADSHEET_ID is not set."
        )

    credentials_path = Path(raw_credentials_path).expanduser()
    if not credentials_path.is_absolute():
        credentials_path = project_root / credentials_path

    if not credentials_path.is_file():
        raise ConfigError(
            "Google credentials file was not found. Check GOOGLE_APPLICATION_CREDENTIALS."
        )

    return AppConfig(
        credentials_path=credentials_path.resolve(),
        spreadsheet_id=spreadsheet_id,
    )
