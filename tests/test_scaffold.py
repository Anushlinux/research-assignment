import sys
from importlib import import_module


def test_project_runs_on_python_312() -> None:
    assert sys.version_info[:2] == (3, 12)


def test_direct_runtime_dependencies_import() -> None:
    module_names = (
        "agents",
        "composio",
        "openai",
        "pydantic",
        "pydantic_settings",
        "rich",
        "tenacity",
        "typer",
    )

    for module_name in module_names:
        assert import_module(module_name) is not None
