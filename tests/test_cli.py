import pytest
from typer.testing import CliRunner

from integration_research.cli import app

runner = CliRunner()


def test_cli_accepts_arbitrary_valid_app_before_credentials_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from integration_research.settings import Settings

    def fail_before_live_calls(_self: Settings) -> None:
        raise ValueError("Missing live credentials in test")

    monkeypatch.setattr(Settings, "require_live_credentials", fail_before_live_calls)
    result = runner.invoke(app, ["run", "--app-id", "22", "--run-id", "valid-app"])
    assert result.exit_code == 1
    assert "Missing live credentials" in result.output
    assert "permits only" not in result.output.lower()


def test_cli_rejects_invalid_or_ambiguous_id_selection() -> None:
    invalid = runner.invoke(app, ["run", "--app-id", "101", "--run-id", "invalid"])
    assert invalid.exit_code == 2
    assert "do not exist in data/apps.csv" in invalid.output

    both = runner.invoke(
        app,
        ["run", "--app-id", "22", "--ids", "22,31", "--run-id", "ambiguous"],
    )
    assert both.exit_code == 2
    assert "exactly one" in both.output


def test_cli_rejects_duplicate_or_malformed_multi_ids() -> None:
    duplicate = runner.invoke(app, ["run", "--ids", "22,22", "--run-id", "duplicate"])
    assert duplicate.exit_code == 2
    assert "duplicates" in duplicate.output

    malformed = runner.invoke(app, ["run", "--ids", "22,nope", "--run-id", "malformed"])
    assert malformed.exit_code == 2
    assert "integers" in malformed.output
