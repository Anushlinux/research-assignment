from __future__ import annotations

from pathlib import Path

import pytest

from integration_research.composio_session import FETCH_TOOL, SEARCH_TOOL, ToolExecution
from integration_research.extraction import ExtractionResult
from integration_research.models import AppResearchDraft, EvidenceRef
from integration_research.pipeline import PipelineFailure, run_github_pipeline
from integration_research.settings import Settings
from integration_research.source_selection import SEARCH_PLANS
from tests.helpers import make_sources, make_valid_draft


class FakeResearchClient:
    session_id = "session-test"

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        sources = make_sources()
        self._texts = {source.url: source.text for source in sources.values()}
        self._titles = {source.url: source.title for source in sources.values()}
        self._search_urls = [source.url for source in sources.values()]

    def execute(self, tool_slug: str, arguments: dict[str, object]) -> ToolExecution:
        self.calls.append((tool_slug, arguments))
        if tool_slug == SEARCH_TOOL:
            query = arguments["query"]
            assert isinstance(query, str)
            plan_index = [plan.query for plan in SEARCH_PLANS].index(query)
            url = self._search_urls[plan_index]
            data: dict[str, object] = {"citations": [{"title": self._titles[url], "url": url}]}
        elif tool_slug == FETCH_TOOL:
            urls = arguments["urls"]
            assert isinstance(urls, list) and len(urls) == 1
            url_value = urls[0]
            assert isinstance(url_value, str)
            data = {
                "results": [
                    {
                        "title": self._titles[url_value],
                        "url": url_value,
                        "text": self._texts[url_value],
                    }
                ]
            }
        else:
            raise AssertionError(f"unexpected tool: {tool_slug}")
        return ToolExecution(
            data=data,
            error=None,
            log_id=f"log-{len(self.calls)}",
            raw_response={"data": data, "error": None},
        )


class FakeExtractionClient:
    model = "fake-structured-model"

    def __init__(self, draft: AppResearchDraft) -> None:
        self.draft = draft
        self.calls = 0

    def extract(self, *, instructions: str, source_input: str) -> ExtractionResult:
        self.calls += 1
        assert "Use only the supplied source content" in instructions
        assert "SOURCE source_1" in source_input
        return ExtractionResult(
            draft=self.draft,
            response_id="response-test",
            input_tokens=123,
            output_tokens=45,
        )


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        runs_dir=tmp_path / "runs",
        state_dir=tmp_path / ".state",
    )


def test_pipeline_uses_only_allowed_calls_and_separates_artifacts(tmp_path: Path) -> None:
    research = FakeResearchClient()
    extraction = FakeExtractionClient(make_valid_draft())
    result = run_github_pipeline(
        settings=make_settings(tmp_path),
        run_id="offline-success",
        research_client=research,
        extraction_client=extraction,
    )

    assert [tool for tool, _arguments in research.calls].count(SEARCH_TOOL) == 4
    assert [tool for tool, _arguments in research.calls].count(FETCH_TOOL) == 4
    assert extraction.calls == 1
    assert result.final.buildability.value == "yes"
    assert result.metrics.browser_calls == 0
    assert result.metrics.input_tokens == 123
    assert (result.app_dir / "draft.json").exists()
    assert (result.app_dir / "validation.json").exists()
    assert (result.app_dir / "final.json").exists()
    assert len(list((result.app_dir / "sources").glob("source_*.json"))) == 4


def test_pipeline_preserves_failure_and_writes_no_final(tmp_path: Path) -> None:
    bad_draft = make_valid_draft()
    bad_draft.description.evidence = [
        EvidenceRef(source_id="source_1", quote="fabricated quotation")
    ]
    research = FakeResearchClient()
    extraction = FakeExtractionClient(bad_draft)
    with pytest.raises(PipelineFailure, match="deterministic validation"):
        run_github_pipeline(
            settings=make_settings(tmp_path),
            run_id="offline-failure",
            research_client=research,
            extraction_client=extraction,
        )

    app_dir = tmp_path / "runs" / "offline-failure" / "apps" / "061-github"
    assert (app_dir / "draft.json").exists()
    assert (app_dir / "validation.json").exists()
    assert (app_dir / "metrics.json").exists()
    assert (app_dir / "failure.json").exists()
    assert not (app_dir / "final.json").exists()
    assert extraction.calls == 1
