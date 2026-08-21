from pathlib import Path


def test_runtime_and_prompts_contain_no_pilot_app_special_cases() -> None:
    root = Path(__file__).resolve().parents[1]
    runtime_text = "\n".join(
        path.read_text(encoding="utf-8")
        for directory in (root / "src", root / "prompts")
        for path in directory.rglob("*.py" if directory.name == "src" else "*.md")
    ).lower()
    for app_name in ("github", "twilio", "google ads", "pitchbook", "mermaid"):
        assert app_name not in runtime_text
