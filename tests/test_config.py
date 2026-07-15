from __future__ import annotations

from pathlib import Path

import pytest

from src.config import ConfigError, load_config


def test_load_config_raises_when_required_env_var_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("GOOGLE_SPREADSHEET_ID", "spreadsheet-id")

    with pytest.raises(ConfigError, match="GOOGLE_APPLICATION_CREDENTIALS"):
        load_config(env_file=Path("missing.env"))


def test_load_config_raises_when_credentials_file_does_not_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing_credentials = tmp_path / "service-account.json"
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(missing_credentials))
    monkeypatch.setenv("GOOGLE_SPREADSHEET_ID", "spreadsheet-id")

    with pytest.raises(ConfigError, match="credentials file was not found"):
        load_config(env_file=tmp_path / ".env")
