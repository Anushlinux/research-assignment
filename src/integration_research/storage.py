"""Run artifact storage for one immutable GitHub attempt."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pydantic import BaseModel

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class RunStorage:
    def __init__(self, *, runs_dir: Path, run_id: str) -> None:
        if not RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError("run_id must be 1-64 letters, numbers, dots, underscores, or hyphens")
        self.app_dir = runs_dir / run_id / "apps" / "061-github"
        self.app_dir.mkdir(parents=True, exist_ok=False)
        (self.app_dir / "sources").mkdir()

    def write_json(self, relative_path: str, value: object) -> Path:
        path = self.app_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite immutable artifact: {path}")
        payload: object = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
        return path
