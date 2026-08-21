"""Synchronous Milestone 1.1 pipeline for GitHub app ID 61."""

from __future__ import annotations

import csv
import hashlib
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict

from integration_research.audit import (
    AUDIT_PROMPT_VERSION,
    AuditClient,
    OpenAIAuditClient,
    apply_semantic_audit,
    build_audit_input,
    load_audit_prompt,
)
from integration_research.composio_session import (
    FETCH_TOOL,
    SEARCH_TOOL,
    ComposioResearchClient,
    ResearchClient,
)
from integration_research.extraction import (
    PROMPT_VERSION,
    ExtractionClient,
    OpenAIExtractionClient,
    load_extraction_prompt,
)
from integration_research.models import (
    AppInput,
    AppResearchDraft,
    FetchedSource,
    FinalAppResearch,
    RunMetrics,
    ValidationReport,
)
from integration_research.reduction import (
    build_evidence_snippets,
    build_source_package,
    reduce_sources,
)
from integration_research.settings import Settings
from integration_research.source_selection import (
    SEARCH_PLANS,
    SearchCandidate,
    candidates_from_citations,
    normalize_url,
    official_source_tier,
    select_sources,
)
from integration_research.storage import RunStorage
from integration_research.validation import validate_draft
from integration_research.verdict import build_final_record

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APPS_CSV = PROJECT_ROOT / "data" / "apps.csv"


class PipelineFailure(RuntimeError):
    """Raised after auditable failure artifacts have been written."""


class PipelineResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    final: FinalAppResearch
    validation: ValidationReport
    metrics: RunMetrics
    app_dir: Path


def load_app(app_id: int) -> AppInput:
    with APPS_CSV.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        for row in rows:
            if int(row["id"]) == app_id:
                return AppInput(
                    app_id=app_id,
                    app_name=row["app_name"],
                    website_hint=row["website_hint"],
                    category=row["category"],
                    notes=row["notes"],
                )
    raise ValueError(f"App ID {app_id} does not exist in data/apps.csv")


def _dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [cast(dict[str, object], item) for item in value if isinstance(item, dict)]


def _elapsed_ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _failure_payload(stage: str, error: Exception) -> dict[str, object]:
    return {
        "stage": stage,
        "error_type": type(error).__name__,
        "message": str(error),
        "recorded_at": datetime.now(UTC).isoformat(),
    }


def run_github_pipeline(
    *,
    settings: Settings,
    run_id: str,
    research_client: ResearchClient | None = None,
    extraction_client: ExtractionClient | None = None,
    audit_client: AuditClient | None = None,
) -> PipelineResult:
    app_input = load_app(61)
    storage = RunStorage(runs_dir=settings.runs_dir, run_id=run_id)
    storage.write_json("input.json", app_input)
    metrics = RunMetrics()
    pipeline_start = time.perf_counter()
    stage = "initialization"

    try:
        client = research_client or ComposioResearchClient(settings)
        extractor = extraction_client or OpenAIExtractionClient(settings)
        auditor = audit_client or OpenAIAuditClient(settings)
        metrics.extraction_model = extractor.model
        metrics.audit_model = auditor.model

        stage = "search"
        search_records: list[dict[str, object]] = []
        all_candidates: list[SearchCandidate] = []
        if settings.research_max_searches_per_app != len(SEARCH_PLANS):
            raise ValueError("Milestone 1.1 requires exactly five configured search calls")

        for plan in SEARCH_PLANS:
            call_start = time.perf_counter()
            metrics.search_calls += 1
            execution = client.execute(SEARCH_TOOL, {"query": plan.query})
            latency = _elapsed_ms(call_start)
            metrics.search_latency_ms += latency
            search_records.append(
                {
                    "source_role": plan.role.value,
                    "query": plan.query,
                    "arguments": {"query": plan.query},
                    "latency_ms": latency,
                    "log_id": execution.log_id,
                    "error": execution.error,
                    "raw_response": execution.raw_response,
                }
            )
            if execution.error is not None:
                raise PipelineFailure(f"Composio search failed: {execution.error}")
            citations = _dict_list(execution.data.get("citations"))
            all_candidates.extend(
                candidates_from_citations(role=plan.role, query=plan.query, citations=citations)
            )
        storage.write_json("searches.json", search_records)

        stage = "source_selection"
        selected = select_sources(all_candidates, maximum=settings.research_max_fetches_per_app)
        if not selected:
            raise PipelineFailure("No allowed official GitHub source was selected")
        selected_records = []
        for index, candidate in enumerate(selected, start=1):
            record = candidate.as_dict()
            record["source_id"] = f"source_{index}"
            selected_records.append(record)
        storage.write_json("selected-sources.json", selected_records)

        stage = "fetch"
        fetched_sources: list[FetchedSource] = []
        for index, candidate in enumerate(selected, start=1):
            source_id = f"source_{index}"
            call_start = time.perf_counter()
            metrics.fetch_calls += 1
            execution = client.execute(
                FETCH_TOOL, {"urls": [candidate.normalized_url], "text": True}
            )
            latency = _elapsed_ms(call_start)
            metrics.fetch_latency_ms += latency
            results = _dict_list(execution.data.get("results"))
            result = results[0] if results else {}
            returned_url = result.get("url", candidate.normalized_url)
            returned_title = result.get("title", candidate.title)
            returned_text = result.get("text", "")
            url = returned_url if isinstance(returned_url, str) else candidate.normalized_url
            title = returned_title if isinstance(returned_title, str) else candidate.title
            text = returned_text if isinstance(returned_text, str) else ""
            tier = official_source_tier(url)
            successful = (
                execution.error is None
                and bool(text.strip())
                and tier is not None
                and normalize_url(url) == candidate.normalized_url
            )
            source = FetchedSource(
                source_id=source_id,
                source_role=candidate.role,
                url=url,
                title=title,
                source_tier=tier or candidate.source_tier,
                text=text,
                successful=successful,
                retrieved_at=datetime.now(UTC),
                content_hash=_sha256(text),
                log_id=execution.log_id,
                raw_response=execution.raw_response,
                latency_ms=latency,
            )
            storage.write_json(f"sources/{source_id}.json", source)
            if successful:
                fetched_sources.append(source)
        if not fetched_sources:
            raise PipelineFailure("Every selected official source failed to fetch")

        stage = "reduction"
        reduced = reduce_sources(
            fetched_sources,
            per_page_limit=settings.research_max_chars_per_page,
            per_app_limit=settings.research_max_chars_per_app,
        )
        snippets = build_evidence_snippets(fetched_sources, reduced)
        if not snippets:
            raise PipelineFailure("Source reduction produced no referenceable evidence snippets")
        storage.write_json(
            "evidence-snippets.json",
            [snippet.model_dump(mode="json") for snippet in snippets.values()],
        )
        source_package = build_source_package(fetched_sources, snippets)
        extraction_prompt = load_extraction_prompt()
        source_input = "\n".join(
            (
                "APP",
                f"app_id: {app_input.app_id}",
                f"app_name: {app_input.app_name}",
                f"category: {app_input.category}",
                "",
                source_package,
            )
        )
        storage.write_json(
            "extraction-input.json",
            {
                "prompt_version": PROMPT_VERSION,
                "prompt_sha256": _sha256(extraction_prompt),
                "model": extractor.model,
                "instructions": extraction_prompt,
                "source_input": source_input,
                "sources": [
                    {
                        "source_id": source.source_id,
                        "source_role": source.source_role.value,
                        "url": source.url,
                        "title": source.title,
                        "content_hash": source.content_hash,
                        "reduced_characters": len(reduced[source.source_id]),
                        "evidence_snippets": sum(
                            snippet.source_id == source.source_id for snippet in snippets.values()
                        ),
                    }
                    for source in fetched_sources
                ],
            },
        )

        stage = "extraction"
        call_start = time.perf_counter()
        metrics.openai_calls += 1
        metrics.extraction_calls += 1
        extraction = extractor.extract(instructions=extraction_prompt, source_input=source_input)
        extraction_latency = _elapsed_ms(call_start)
        metrics.openai_latency_ms += extraction_latency
        metrics.extraction_latency_ms += extraction_latency
        metrics.extraction_input_tokens = extraction.input_tokens
        metrics.extraction_output_tokens = extraction.output_tokens
        metrics.input_tokens += extraction.input_tokens
        metrics.output_tokens += extraction.output_tokens
        raw_draft: AppResearchDraft = extraction.draft
        storage.write_json("draft.json", raw_draft)
        storage.write_json(
            "extraction-response.json",
            {
                "response_id": extraction.response_id,
                "model": extractor.model,
                "input_tokens": extraction.input_tokens,
                "output_tokens": extraction.output_tokens,
            },
        )

        sources_by_id = {source.source_id: source for source in fetched_sources}
        stage = "literal_validation"
        literal_validation = validate_draft(
            raw_draft,
            app_input=app_input,
            sources=sources_by_id,
            snippets=snippets,
        )
        storage.write_json("literal-validation.json", literal_validation)
        if not literal_validation.valid:
            raise PipelineFailure(
                "Draft failed fatal literal validation with "
                f"{len(literal_validation.errors)} error(s)"
            )

        stage = "semantic_audit"
        audit_input = build_audit_input(raw_draft, sources_by_id, snippets)
        audit_prompt = load_audit_prompt()
        storage.write_json(
            "semantic-audit-input.json",
            {
                "prompt_version": AUDIT_PROMPT_VERSION,
                "prompt_sha256": _sha256(audit_prompt),
                "model": auditor.model,
                "instructions": audit_prompt,
                "audit_input": audit_input.model_dump(mode="json"),
            },
        )
        call_start = time.perf_counter()
        metrics.openai_calls += 1
        metrics.audit_calls += 1
        audit_execution = auditor.audit(instructions=audit_prompt, audit_input=audit_input)
        audit_latency = _elapsed_ms(call_start)
        metrics.openai_latency_ms += audit_latency
        metrics.audit_latency_ms += audit_latency
        metrics.audit_input_tokens = audit_execution.input_tokens
        metrics.audit_output_tokens = audit_execution.output_tokens
        metrics.input_tokens += audit_execution.input_tokens
        metrics.output_tokens += audit_execution.output_tokens
        storage.write_json("semantic-audit.json", audit_execution.response)
        storage.write_json(
            "semantic-audit-response.json",
            {
                "response_id": audit_execution.response_id,
                "model": auditor.model,
                "input_tokens": audit_execution.input_tokens,
                "output_tokens": audit_execution.output_tokens,
            },
        )

        stage = "admission"
        admitted_draft, admission = apply_semantic_audit(
            raw_draft,
            audit_input,
            audit_execution.response,
        )
        storage.write_json("admission-diff.json", admission)
        storage.write_json("admitted-draft.json", admitted_draft)

        stage = "final_validation"
        final_validation = validate_draft(
            admitted_draft,
            app_input=app_input,
            sources=sources_by_id,
            snippets=snippets,
        )
        storage.write_json("final-validation.json", final_validation)
        if not final_validation.valid:
            raise PipelineFailure(
                "Admitted draft failed deterministic validation with "
                f"{len(final_validation.errors)} error(s)"
            )

        stage = "finalization"
        final = build_final_record(
            draft=admitted_draft,
            app_input=app_input,
            sources=sources_by_id,
            snippets=snippets,
            extraction_model=extractor.model,
            audit_model=auditor.model,
        )
        storage.write_json("final.json", final)
        metrics.total_latency_ms = _elapsed_ms(pipeline_start)
        storage.write_json("metrics.json", metrics)
        return PipelineResult(
            final=final,
            validation=final_validation,
            metrics=metrics,
            app_dir=storage.app_dir.resolve(),
        )
    except Exception as error:
        metrics.total_latency_ms = _elapsed_ms(pipeline_start)
        with suppress(FileExistsError):
            storage.write_json("metrics.json", metrics)
        storage.write_json("failure.json", _failure_payload(stage, error))
        if isinstance(error, PipelineFailure):
            raise
        raise PipelineFailure(f"{stage} failed: {error}") from error
