"""Restricted Composio SDK session used by the direct research path."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from composio import SESSION_PRESET_DIRECT_TOOLS, Composio

from integration_research.settings import Settings

SEARCH_TOOL = "COMPOSIO_SEARCH_WEB"
FETCH_TOOL = "COMPOSIO_SEARCH_FETCH_URL_CONTENT"
ALLOWED_TOOLS = frozenset({SEARCH_TOOL, FETCH_TOOL})


@dataclass(frozen=True)
class ToolExecution:
    data: dict[str, object]
    error: str | None
    log_id: str
    raw_response: dict[str, object]


class ResearchClient(Protocol):
    session_id: str

    def execute(self, tool_slug: str, arguments: dict[str, object]) -> ToolExecution: ...


class ComposioResearchClient:
    """Create or reuse one session containing only the two approved tools."""

    def __init__(self, settings: Settings) -> None:
        if settings.composio_api_key is None:
            raise ValueError("COMPOSIO_API_KEY is required")
        self._settings = settings
        self._composio = Composio(
            api_key=settings.composio_api_key.get_secret_value(), max_retries=0
        )
        session_id = settings.composio_session_id or self._read_stored_session_id()
        if session_id:
            self._session = self._composio.sessions.use(session_id, mcp=False)
        else:
            self._session = self._composio.sessions.create(
                user_id=settings.composio_user_id,
                toolkits=["composio_search"],
                tools={
                    "composio_search": {
                        "enable": [SEARCH_TOOL, FETCH_TOOL],
                    }
                },
                session_preset=SESSION_PRESET_DIRECT_TOOLS,
                mcp=False,
            )
            self._store_session_id(self._session.session_id)
        self.session_id = self._session.session_id

    @property
    def _state_path(self) -> Path:
        return self._settings.state_dir / "composio_session.json"

    def _read_stored_session_id(self) -> str:
        if not self._state_path.exists():
            return ""
        payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        value = payload.get("session_id", "")
        return value if isinstance(value, str) else ""

    def _store_session_id(self, session_id: str) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "session_id": session_id,
            "user_id": self._settings.composio_user_id,
            "allowed_tools": sorted(ALLOWED_TOOLS),
        }
        self._state_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def execute(self, tool_slug: str, arguments: dict[str, object]) -> ToolExecution:
        if tool_slug not in ALLOWED_TOOLS:
            raise ValueError(f"Tool is outside the restricted research session: {tool_slug}")
        response = self._session.execute(tool_slug, arguments=arguments)
        raw: dict[str, object] = response.model_dump(mode="json")
        data: dict[str, object] = response.data
        return ToolExecution(
            data=data,
            error=response.error,
            log_id=response.log_id,
            raw_response=raw,
        )
