from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from src.google_sheets import GoogleSheetsAPIError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def _load_script_module(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


smoke_write = _load_script_module("smoke_test_sheets_write")
smoke_read = _load_script_module("smoke_test_sheets")


def _stub_client_factory(monkeypatch: pytest.MonkeyPatch, module: ModuleType, client: MagicMock) -> None:
    monkeypatch.setattr(module, "load_config", lambda: object())
    monkeypatch.setattr(
        module.GoogleSheetsClient,
        "from_config",
        staticmethod(lambda config, scopes=None: client),
    )


# --- Write smoke-test script -------------------------------------------------


def test_write_smoke_test_reports_success_only_after_cleanup(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client = MagicMock()
    client.read_range.return_value = [
        ["Name", "Phone", "Notes"],
        ["Alice", "+7 999 123-45-67", "RAW input check"],
    ]
    _stub_client_factory(monkeypatch, smoke_write, client)

    exit_code = smoke_write.main()

    assert exit_code == 0
    client.create_sheet.assert_called_once()
    client.delete_sheet.assert_called_once()
    captured = capsys.readouterr()
    assert "Write smoke-test completed successfully." in captured.out


def test_write_smoke_test_cleanup_failure_returns_nonzero_and_does_not_claim_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client = MagicMock()
    client.read_range.return_value = [
        ["Name", "Phone", "Notes"],
        ["Alice", "+7 999 123-45-67", "RAW input check"],
    ]
    client.delete_sheet.side_effect = GoogleSheetsAPIError("delete failed")
    _stub_client_factory(monkeypatch, smoke_write, client)

    exit_code = smoke_write.main()

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "Cleanup failed" in captured.err
    assert "completed successfully" not in captured.out


def test_write_smoke_test_operation_failure_still_attempts_cleanup(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client = MagicMock()
    client.write_range.side_effect = GoogleSheetsAPIError("write failed")
    _stub_client_factory(monkeypatch, smoke_write, client)

    exit_code = smoke_write.main()

    assert exit_code != 0
    client.delete_sheet.assert_called_once()
    captured = capsys.readouterr()
    assert "completed successfully" not in captured.out


# --- Read smoke-test script ---------------------------------------------------


def test_read_smoke_test_requires_explicit_worksheet_argument() -> None:
    with pytest.raises(SystemExit):
        smoke_read.parse_args([])


def test_read_smoke_test_uses_bounded_default_range_and_hides_values_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client = MagicMock()
    client.get_sheet_names.return_value = ["Quarterly Report"]
    client.read_range.return_value = [["A", "B"], ["1", "2"]]
    _stub_client_factory(monkeypatch, smoke_read, client)

    exit_code = smoke_read.main(["Quarterly Report"])

    assert exit_code == 0
    client.read_range.assert_called_once_with("'Quarterly Report'!A1:E5")
    client.read_all_values.assert_not_called()
    captured = capsys.readouterr()
    assert "['A', 'B']" not in captured.out
    assert "['1', '2']" not in captured.out


def test_read_smoke_test_shows_values_only_when_explicitly_requested(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client = MagicMock()
    client.get_sheet_names.return_value = ["Quarterly Report"]
    client.read_range.return_value = [["A", "B"]]
    _stub_client_factory(monkeypatch, smoke_read, client)

    exit_code = smoke_read.main(["Quarterly Report", "--show-values"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "['A', 'B']" in captured.out


def test_read_smoke_test_fails_cleanly_for_unknown_worksheet(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client = MagicMock()
    client.get_sheet_names.return_value = ["Other Sheet"]
    _stub_client_factory(monkeypatch, smoke_read, client)

    exit_code = smoke_read.main(["Missing Sheet"])

    assert exit_code == 1
    client.read_range.assert_not_called()
