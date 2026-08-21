from typer.testing import CliRunner

from integration_research.cli import app

runner = CliRunner()


def test_cli_exposes_run_subcommand_and_rejects_non_github_app() -> None:
    result = runner.invoke(app, ["run", "--app-id", "22", "--run-id", "must-reject"])
    assert result.exit_code == 2
    assert "Milestone 1.1 permits only GitHub app ID 61" in result.output
