"""Command-line entry point for the bounded Milestone 1 run."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from integration_research.pipeline import PipelineFailure, run_github_pipeline
from integration_research.settings import Settings

app = typer.Typer(no_args_is_help=True, help="Evidence-backed integration research")
console = Console()


@app.callback()
def main() -> None:
    """Run bounded evidence-backed integration research commands."""


@app.command("run")
def run_command(
    app_id: Annotated[int, typer.Option("--app-id", help="Must be GitHub app ID 61")],
    run_id: Annotated[str, typer.Option("--run-id", help="Immutable run identifier")],
) -> None:
    """Run the synchronous GitHub-only Milestone 1.1 production path."""

    if app_id != 61:
        raise typer.BadParameter(
            "Milestone 1.1 permits only GitHub app ID 61", param_hint="--app-id"
        )
    settings = Settings()
    try:
        settings.require_live_credentials()
        result = run_github_pipeline(settings=settings, run_id=run_id)
    except (ValueError, FileExistsError, PipelineFailure) as error:
        console.print(f"[red]Milestone 1.1 failed:[/red] {error}")
        raise typer.Exit(code=1) from error

    console.print(f"[green]GitHub final record:[/green] {result.app_dir / 'final.json'}")
    console.print(
        f"Validation: {len(result.validation.errors)} errors, "
        f"{len(result.validation.warnings)} warnings; "
        f"buildability={result.final.buildability.value}"
    )


if __name__ == "__main__":
    app()
