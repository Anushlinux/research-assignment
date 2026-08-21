from pathlib import Path

from integration_research.models import AppInput
from integration_research.storage import RunStorage, app_artifact_name


def catalog_app(app_id: int, name: str) -> AppInput:
    return AppInput(
        app_id=app_id,
        app_name=name,
        website_hint="example.test",
        category="Example",
        notes="",
    )


def test_artifact_paths_derive_from_app_id_and_name(tmp_path: Path) -> None:
    first = catalog_app(22, "Message Service")
    second = catalog_app(98, "Diagram CLI")
    assert app_artifact_name(first) == "022-message-service"
    assert app_artifact_name(second) == "098-diagram-cli"

    first_storage = RunStorage(runs_dir=tmp_path, run_id="sequential", app=first)
    second_storage = RunStorage(runs_dir=tmp_path, run_id="sequential", app=second)
    assert first_storage.app_dir != second_storage.app_dir
    assert first_storage.app_dir.is_dir()
    assert second_storage.app_dir.is_dir()
