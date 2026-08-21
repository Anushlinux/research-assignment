from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from integration_research.audit import AuditClient, AuditExecution
from integration_research.composio_session import (
    FETCH_TOOL,
    SEARCH_TOOL,
    ResearchClient,
    ToolExecution,
)
from integration_research.extraction import ExtractionClient, ExtractionResult
from integration_research.models import (
    AppResearchDraft,
    AuditDecision,
    Buildability,
    ClaimAuditResult,
    CommercialRequirement,
    EvidenceRef,
    FinalAppResearch,
    RunMetrics,
    SemanticAuditInput,
    SemanticAuditResponse,
    ValidationReport,
)
from integration_research.pipeline import (
    PipelineFailure,
    PipelineResult,
    run_app_pipeline,
    run_app_sequence,
)
from integration_research.settings import Settings
from integration_research.source_selection import build_search_plans
from tests.helpers import make_app_input, make_sources, make_valid_draft


class FakeResearchClient:
    session_id = "session-test"

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        sources = make_sources()
        self._texts = {source.url: source.text for source in sources.values()}
        self._titles = {source.url: source.title for source in sources.values()}
        self._search_urls = [source.url for source in sources.values()]
        self._plans = build_search_plans(make_app_input())

    def execute(self, tool_slug: str, arguments: dict[str, object]) -> ToolExecution:
        self.calls.append((tool_slug, arguments))
        if tool_slug == SEARCH_TOOL:
            query = arguments["query"]
            assert isinstance(query, str)
            plan_index = [plan.query for plan in self._plans].index(query)
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
        assert "Use only supplied source content" in instructions
        assert "SOURCE source_1" in source_input
        assert "ROLES: authentication" in source_input
        return ExtractionResult(
            draft=self.draft,
            response_id="response-test",
            input_tokens=123,
            output_tokens=45,
        )


class FakeAuditClient:
    model = "fake-audit-model"

    def __init__(self, *, unsupported_field: str | None = None, incomplete: bool = False) -> None:
        self.unsupported_field = unsupported_field
        self.incomplete = incomplete
        self.calls = 0

    def audit(self, *, instructions: str, audit_input: SemanticAuditInput) -> AuditExecution:
        self.calls += 1
        assert "Do not browse" in instructions
        results = []
        for claim in audit_input.claims:
            decision = (
                AuditDecision.UNSUPPORTED
                if claim.field == self.unsupported_field
                else AuditDecision.DIRECT_SUPPORT
            )
            results.append(
                ClaimAuditResult(
                    claim_id=claim.claim_id,
                    decision=decision,
                    reason="The supplied evidence was evaluated independently.",
                )
            )
        if self.incomplete:
            results.pop()
        return AuditExecution(
            response=SemanticAuditResponse(results=results),
            response_id="audit-response-test",
            input_tokens=67,
            output_tokens=23,
        )


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        runs_dir=tmp_path / "runs",
        state_dir=tmp_path / ".state",
        research_max_searches_per_app=5,
        research_max_fetches_per_app=5,
    )


def test_pipeline_uses_bounded_calls_and_separates_audit_artifacts(tmp_path: Path) -> None:
    research = FakeResearchClient()
    extraction = FakeExtractionClient(make_valid_draft())
    audit = FakeAuditClient()
    result = run_app_pipeline(
        settings=make_settings(tmp_path),
        run_id="offline-success",
        app_id=61,
        research_client=research,
        extraction_client=extraction,
        audit_client=audit,
    )

    assert [tool for tool, _arguments in research.calls].count(SEARCH_TOOL) == 5
    assert [tool for tool, _arguments in research.calls].count(FETCH_TOOL) == 5
    assert extraction.calls == 1
    assert audit.calls == 1
    assert result.final.buildability.value == "yes"
    assert result.metrics.browser_calls == 0
    assert result.metrics.openai_calls == 2
    assert result.metrics.input_tokens == 190
    for artifact in (
        "draft.json",
        "normalized-draft.json",
        "evidence-snippets.json",
        "literal-validation.json",
        "semantic-audit-input.json",
        "semantic-audit.json",
        "admission-diff.json",
        "admitted-draft.json",
        "final-validation.json",
        "final.json",
    ):
        assert (result.app_dir / artifact).exists()
    assert len(list((result.app_dir / "sources").glob("source_*.json"))) == 5


def test_unsupported_claim_is_downgraded_and_final_is_written(tmp_path: Path) -> None:
    result = run_app_pipeline(
        settings=make_settings(tmp_path),
        run_id="offline-downgrade",
        app_id=61,
        research_client=FakeResearchClient(),
        extraction_client=FakeExtractionClient(make_valid_draft()),
        audit_client=FakeAuditClient(unsupported_field="commercial_requirement"),
    )
    assert result.final.commercial_requirement.value == CommercialRequirement.UNKNOWN
    assert result.final.buildability.value == "yes"
    assert "commercial_requirement" in result.validation.unknown_fields
    assert (result.app_dir / "final.json").exists()


def test_literal_failure_is_fatal_and_writes_no_final(tmp_path: Path) -> None:
    bad_draft = make_valid_draft()
    bad_draft.description.evidence = [
        EvidenceRef(source_id="source_1", snippet_id="source_1_snippet_999")
    ]
    audit = FakeAuditClient()
    with pytest.raises(PipelineFailure, match="fatal literal validation"):
        run_app_pipeline(
            settings=make_settings(tmp_path),
            run_id="offline-failure",
            app_id=61,
            research_client=FakeResearchClient(),
            extraction_client=FakeExtractionClient(bad_draft),
            audit_client=audit,
        )

    app_dir = tmp_path / "runs" / "offline-failure" / "apps" / "061-github"
    assert (app_dir / "draft.json").exists()
    assert (app_dir / "literal-validation.json").exists()
    assert (app_dir / "failure.json").exists()
    assert not (app_dir / "final.json").exists()
    assert audit.calls == 0


def test_incomplete_audit_is_fatal_and_preserved(tmp_path: Path) -> None:
    with pytest.raises(PipelineFailure, match="semantic audit is incomplete"):
        run_app_pipeline(
            settings=make_settings(tmp_path),
            run_id="offline-incomplete-audit",
            app_id=61,
            research_client=FakeResearchClient(),
            extraction_client=FakeExtractionClient(make_valid_draft()),
            audit_client=FakeAuditClient(incomplete=True),
        )
    app_dir = tmp_path / "runs" / "offline-incomplete-audit" / "apps" / "061-github"
    assert (app_dir / "semantic-audit.json").exists()
    assert (app_dir / "failure.json").exists()
    assert not (app_dir / "admitted-draft.json").exists()
    assert not (app_dir / "final.json").exists()


def test_sequential_run_continues_after_one_app_failure(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)

    def fake_runner(**kwargs: object) -> PipelineResult:
        app_id = cast(int, kwargs["app_id"])
        app_name = "GitHub" if app_id == 61 else "Twilio"
        app_dir = settings.runs_dir / "sequential" / "apps" / f"{app_id:03d}-{app_name.lower()}"
        app_dir.mkdir(parents=True)
        if app_id == 61:
            (app_dir / "failure.json").write_text("{}\n", encoding="utf-8")
            raise PipelineFailure("simulated first-app failure")
        (app_dir / "final.json").write_text("{}\n", encoding="utf-8")
        final = FinalAppResearch.model_construct(
            app_id=app_id,
            app_name=app_name,
            buildability=Buildability.YES,
        )
        return PipelineResult.model_construct(
            final=final,
            validation=ValidationReport(
                valid=True,
                errors=[],
                warnings=[],
                normalizations=[],
                unknown_fields=[],
            ),
            metrics=RunMetrics(),
            app_dir=app_dir,
        )

    result = run_app_sequence(
        settings=settings,
        run_id="sequential",
        app_ids=[61, 22],
        research_client=cast(ResearchClient, object()),
        extraction_client=cast(ExtractionClient, object()),
        audit_client=cast(AuditClient, object()),
        pipeline_runner=fake_runner,
    )
    assert [item.final.app_id for item in result.completed] == [22]
    assert [item["app_id"] for item in result.failures] == [61]
    assert result.summary_path.exists()
    assert result.pilot_summary_path.exists()
    assert (settings.runs_dir / "sequential" / "apps" / "061-github" / "failure.json").exists()
    assert (settings.runs_dir / "sequential" / "apps" / "022-twilio" / "final.json").exists()
