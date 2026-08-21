"""One tool-free OpenAI structured extraction call over fetched sources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from openai import OpenAI

from integration_research.models import AppResearchDraft
from integration_research.settings import Settings

PROMPT_VERSION = "github-extract-v3"
PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extract.md"


@dataclass(frozen=True)
class ExtractionResult:
    draft: AppResearchDraft
    response_id: str
    input_tokens: int
    output_tokens: int


class ExtractionClient(Protocol):
    model: str

    def extract(self, *, instructions: str, source_input: str) -> ExtractionResult: ...


class OpenAIExtractionClient:
    def __init__(self, settings: Settings) -> None:
        if settings.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is required")
        self.model = settings.openai_model_extract
        self._client = OpenAI(api_key=settings.openai_api_key.get_secret_value(), max_retries=0)

    def extract(self, *, instructions: str, source_input: str) -> ExtractionResult:
        response = self._client.responses.parse(
            model=self.model,
            instructions=instructions,
            input=source_input,
            reasoning={"effort": "low"},
            text_format=AppResearchDraft,
        )
        draft = response.output_parsed
        if draft is None:
            raise RuntimeError("OpenAI returned no parsed AppResearchDraft")
        usage = response.usage
        return ExtractionResult(
            draft=draft,
            response_id=response.id,
            input_tokens=usage.input_tokens if usage is not None else 0,
            output_tokens=usage.output_tokens if usage is not None else 0,
        )


def load_extraction_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")
