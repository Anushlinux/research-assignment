"""Command-line entry point for bounded catalog research."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from integration_research.pipeline import PipelineFailure, load_app_catalog, run_app_sequence
from integration_research.settings import Settings

app = typer.Typer(no_args_is_help=True, help="Evidence-backed integration research")
console = Console()


@app.callback()
def main() -> None:
    """Run bounded evidence-backed integration research commands."""


@app.command("run")
def run_command(
    run_id: Annotated[str, typer.Option("--run-id", help="Immutable run identifier")],
    app_id: Annotated[
        int | None, typer.Option("--app-id", help="One ID from data/apps.csv")
    ] = None,
    ids: Annotated[
        str | None,
        typer.Option("--ids", help="Comma-separated IDs, executed sequentially"),
    ] = None,
    all_apps: Annotated[
        bool,
        typer.Option("--all", help="Run every app in data/apps.csv sequentially"),
    ] = False,
) -> None:
    """Run one or more catalog apps sequentially with isolated artifacts."""

    selection_count = sum((app_id is not None, ids is not None, all_apps))
    if selection_count != 1:
        raise typer.BadParameter("Provide exactly one of --app-id, --ids, or --all")
    catalog = load_app_catalog()
    if app_id is not None:
        app_ids = [app_id]
    elif all_apps:
        app_ids = sorted(catalog)
    else:
        assert ids is not None
        parts = [part.strip() for part in ids.split(",")]
        if not parts or any(not part for part in parts):
            raise typer.BadParameter("--ids must be a non-empty comma-separated list")
        try:
            app_ids = [int(part) for part in parts]
        except ValueError as error:
            raise typer.BadParameter("--ids values must be integers") from error
    if len(app_ids) != len(set(app_ids)):
        raise typer.BadParameter("App IDs must not contain duplicates")

    missing = [selected_id for selected_id in app_ids if selected_id not in catalog]
    if missing:
        raise typer.BadParameter(
            f"App IDs do not exist in data/apps.csv: {', '.join(map(str, missing))}"
        )
    settings = Settings()
    try:
        settings.require_live_credentials()
        result = run_app_sequence(settings=settings, run_id=run_id, app_ids=app_ids)
    except (ValueError, FileExistsError, PipelineFailure) as error:
        console.print(f"[red]Research run failed:[/red] {error}")
        raise typer.Exit(code=1) from error

    for completed in result.completed:
        console.print(
            f"[green]{completed.final.app_name} final record:[/green] "
            f"{completed.app_dir / 'final.json'}"
        )
        console.print(
            f"Validation: {len(completed.validation.errors)} errors, "
            f"{len(completed.validation.warnings)} warnings; "
            f"buildability={completed.final.buildability.value}"
        )
    for failure in result.failures:
        console.print(f"[red]{failure['app_name']} failed:[/red] {failure['message']}")
    console.print(f"Run summary: {result.summary_path}")
    console.print(f"Pilot comparison: {result.pilot_summary_path}")
    if result.failures:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
