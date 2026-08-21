"""Synchronous, catalog-driven research pipeline."""

from __future__ import annotations

import csv
import hashlib
import json
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
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
    AuditDecision,
    FetchedSource,
    FinalAppResearch,
    RunMetrics,
    SourceRole,
    ValidationReport,
)
from integration_research.reduction import (
    build_evidence_snippets,
    build_source_package,
    reduce_sources,
)
from integration_research.settings import Settings
from integration_research.source_selection import (
    SearchCandidate,
    build_search_plans,
    candidates_from_citations,
    candidates_from_trusted_seeds,
    derive_trusted_source_policy,
    official_source_tier,
    select_sources,
)
from integration_research.storage import RunStorage, app_artifact_name, write_run_json
from integration_research.validation import (
    is_unknown,
    normalize_unknown_questions,
    validate_draft,
)
from integration_research.verdict import build_final_record, explain_buildability

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


@dataclass(frozen=True)
class SequentialRunResult:
    completed: tuple[PipelineResult, ...]
    failures: tuple[dict[str, object], ...]
    summary_path: Path
    pilot_summary_path: Path


def load_app_catalog(path: Path = APPS_CSV) -> dict[int, AppInput]:
    expected = ["id", "app_name", "website_hint", "category", "notes"]
    catalog: dict[int, AppInput] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        if rows.fieldnames != expected:
            raise ValueError(f"apps.csv header must be {expected}")
        for line_number, row in enumerate(rows, start=2):
            try:
                app_id = int(row["id"])
            except (TypeError, ValueError) as error:
                raise ValueError(f"apps.csv line {line_number} has an invalid id") from error
            if app_id in catalog:
                raise ValueError(f"apps.csv contains duplicate app ID {app_id}")
            if not row["app_name"].strip() or not row["category"].strip():
                raise ValueError(f"apps.csv line {line_number} requires app_name and category")
            catalog[app_id] = AppInput(
                app_id=app_id,
                app_name=row["app_name"],
                website_hint=row["website_hint"],
                category=row["category"],
                notes=row["notes"],
            )
    return catalog


def load_app(app_id: int) -> AppInput:
    try:
        return load_app_catalog()[app_id]
    except KeyError as error:
        raise ValueError(f"App ID {app_id} does not exist in data/apps.csv") from error


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


def run_app_pipeline(
    *,
    settings: Settings,
    run_id: str,
    app_id: int,
    research_client: ResearchClient | None = None,
    extraction_client: ExtractionClient | None = None,
    audit_client: AuditClient | None = None,
) -> PipelineResult:
    app_input = load_app(app_id)
    policy = derive_trusted_source_policy(app_input)
    search_plans = build_search_plans(app_input, policy)
    storage = RunStorage(runs_dir=settings.runs_dir, run_id=run_id, app=app_input)
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
        all_candidates: list[SearchCandidate] = candidates_from_trusted_seeds(
            app=app_input,
            policy=policy,
            plans=search_plans,
        )
        if settings.research_max_searches_per_app < len(search_plans):
            raise ValueError(
                f"research_max_searches_per_app must allow {len(search_plans)} required roles"
            )

        for index, plan in enumerate(search_plans, start=1):
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
            storage.write_json(f"searches/{index:02d}-{plan.role.value}.json", search_records[-1])
            if execution.error is not None:
                raise PipelineFailure(f"Composio search failed: {execution.error}")
            citations = _dict_list(execution.data.get("citations"))
            all_candidates.extend(
                candidates_from_citations(
                    policy=policy,
                    role=plan.role,
                    query=plan.query,
                    citations=citations,
                )
            )
        storage.write_json("searches.json", search_records)

        stage = "source_selection"
        selected = select_sources(all_candidates, maximum=settings.research_max_fetches_per_app)
        if not selected:
            raise PipelineFailure("No catalog-trusted source was selected")
        selected_records: list[dict[str, object]] = []
        unique_selected: list[SearchCandidate] = []
        source_id_by_url: dict[str, str] = {}
        roles_by_url: dict[str, list[SourceRole]] = {}
        for candidate in selected:
            if candidate.normalized_url not in source_id_by_url:
                source_id_by_url[candidate.normalized_url] = f"source_{len(unique_selected) + 1}"
                unique_selected.append(candidate)
                roles_by_url[candidate.normalized_url] = []
            roles_by_url[candidate.normalized_url].append(candidate.role)
            record = candidate.as_dict()
            record["source_id"] = source_id_by_url[candidate.normalized_url]
            selected_records.append(record)
        storage.write_json("selected-sources.json", selected_records)

        stage = "fetch"
        fetched_sources: list[FetchedSource] = []
        for candidate in unique_selected:
            source_id = source_id_by_url[candidate.normalized_url]
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
            tier = official_source_tier(url, policy)
            successful = (
                execution.error is None
                and bool(text.strip())
                and tier is not None
                and policy.trusts_url(url)
            )
            source = FetchedSource(
                source_id=source_id,
                source_role=candidate.role,
                source_roles=roles_by_url[candidate.normalized_url],
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
                f"website_hint: {app_input.website_hint}",
                f"notes: {app_input.notes}",
                "The website hint and notes are identity context, not fetched evidence.",
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

        normalized_draft, normalization_issues = normalize_unknown_questions(raw_draft)
        storage.write_json("normalized-draft.json", normalized_draft)
        sources_by_id = {source.source_id: source for source in fetched_sources}
        stage = "literal_validation"
        literal_validation = validate_draft(
            normalized_draft,
            app_input=app_input,
            sources=sources_by_id,
            snippets=snippets,
            normalizations=normalization_issues,
        )
        storage.write_json("literal-validation.json", literal_validation)
        if not literal_validation.valid:
            raise PipelineFailure(
                "Draft failed fatal literal validation with "
                f"{len(literal_validation.errors)} error(s)"
            )

        stage = "semantic_audit"
        audit_input = build_audit_input(normalized_draft, sources_by_id, snippets)
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
            normalized_draft,
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
            normalizations=normalization_issues,
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
            official_domains=list(policy.seed_hosts),
        )
        storage.write_json("final.json", final)
        metrics.total_latency_ms = _elapsed_ms(pipeline_start)
        storage.write_json("metrics.json", metrics)
        audit_counts = (
            {
                decision.value: sum(
                    result.decision == decision for result in audit_execution.response.results
                )
                for decision in AuditDecision
            }
            if audit_execution.response.results
            else {}
        )
        storage.write_json(
            "report.json",
            {
                "app_id": app_input.app_id,
                "app_name": app_input.app_name,
                "queries": [record["query"] for record in search_records],
                "selected_sources_by_role": selected_records,
                "fields_extracted": raw_draft.model_dump(mode="json"),
                "semantic_audit_counts": audit_counts,
                "fields_downgraded_to_unknown": [
                    change.field for change in admission.changes if is_unknown(change.new_value)
                ],
                "unknown_fields": final_validation.unknown_fields,
                "unresolved_questions": admitted_draft.unresolved_questions,
                "buildability": final.buildability.value,
                "buildability_explanation": explain_buildability(admitted_draft),
                "validation_errors": [
                    issue.model_dump(mode="json") for issue in final_validation.errors
                ],
                "validation_warnings": [
                    issue.model_dump(mode="json") for issue in final_validation.warnings
                ],
                "validation_normalizations": [
                    issue.model_dump(mode="json") for issue in final_validation.normalizations
                ],
                "metrics": metrics.model_dump(mode="json"),
            },
        )
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


def run_app_sequence(
    *,
    settings: Settings,
    run_id: str,
    app_ids: list[int],
    research_client: ResearchClient | None = None,
    extraction_client: ExtractionClient | None = None,
    audit_client: AuditClient | None = None,
    pipeline_runner: Callable[..., PipelineResult] | None = None,
) -> SequentialRunResult:
    """Run validated app IDs in order, preserving failures and continuing sequentially."""

    if not app_ids:
        raise ValueError("At least one app ID is required")
    if len(app_ids) != len(set(app_ids)):
        raise ValueError("App IDs must not contain duplicates")
    catalog = load_app_catalog()
    missing = [app_id for app_id in app_ids if app_id not in catalog]
    if missing:
        joined = ", ".join(str(app_id) for app_id in missing)
        raise ValueError(f"App IDs do not exist in data/apps.csv: {joined}")

    client = research_client or ComposioResearchClient(settings)
    extractor = extraction_client or OpenAIExtractionClient(settings)
    auditor = audit_client or OpenAIAuditClient(settings)
    selected_runner = pipeline_runner or run_app_pipeline
    completed: list[PipelineResult] = []
    failures: list[dict[str, object]] = []

    for app_id in app_ids:
        app_input = catalog[app_id]
        try:
            completed.append(
                selected_runner(
                    settings=settings,
                    run_id=run_id,
                    app_id=app_id,
                    research_client=client,
                    extraction_client=extractor,
                    audit_client=auditor,
                )
            )
        except Exception as error:
            failures.append(
                {
                    "app_id": app_id,
                    "app_name": app_input.app_name,
                    "artifact_path": str(
                        (
                            settings.runs_dir / run_id / "apps" / app_artifact_name(app_input)
                        ).resolve()
                    ),
                    "error_type": type(error).__name__,
                    "message": str(error),
                }
            )

    summary = {
        "run_id": run_id,
        "requested_ids": app_ids,
        "completed": [
            {
                "app_id": result.final.app_id,
                "app_name": result.final.app_name,
                "artifact_path": str(result.app_dir),
                "buildability": result.final.buildability.value,
            }
            for result in completed
        ],
        "failed": failures,
        "pilot_summary_path": str((settings.runs_dir / run_id / "pilot-summary.json").resolve()),
    }
    summary_path = write_run_json(
        runs_dir=settings.runs_dir,
        run_id=run_id,
        relative_path="run-summary.json",
        value=summary,
    ).resolve()
    app_reports = [
        json.loads((result.app_dir / "report.json").read_text(encoding="utf-8"))
        for result in completed
        if (result.app_dir / "report.json").exists()
    ]
    failure_details: list[dict[str, object]] = []
    for failure in failures:
        failure_path = Path(str(failure["artifact_path"])) / "failure.json"
        detail = dict(failure)
        if failure_path.exists():
            stored = json.loads(failure_path.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                detail.update(stored)
        failure_details.append(detail)

    def failed_at(*stages: str) -> list[int]:
        return [
            cast(int, failure["app_id"])
            for failure in failure_details
            if failure.get("stage") in stages
        ]

    deeper_research = [
        cast(int, report["app_id"]) for report in app_reports if report.get("unresolved_questions")
    ]
    verifier_candidates = [
        cast(int, report["app_id"])
        for report in app_reports
        if report.get("unresolved_questions")
        or any(
            cast(dict[str, int], report.get("semantic_audit_counts", {})).get(decision, 0)
            for decision in ("partial_support", "unsupported")
        )
    ]
    browser_candidates = set(failed_at("fetch", "reduction"))
    for report in app_reports:
        selected_roles = {
            source.get("source_role")
            for source in cast(list[dict[str, object]], report.get("selected_sources_by_role", []))
        }
        unknown_fields = cast(list[str], report.get("unknown_fields", []))
        if len(unknown_fields) >= 8 and not {
            "authentication",
            "credential_access",
        }.intersection(selected_roles):
            browser_candidates.add(cast(int, report["app_id"]))
    pilot_summary_path = write_run_json(
        runs_dir=settings.runs_dir,
        run_id=run_id,
        relative_path="pilot-summary.json",
        value={
            "run_id": run_id,
            "requested_ids": app_ids,
            "apps": app_reports,
            "schema_failures": failed_at(
                "extraction", "literal_validation", "final_validation", "finalization"
            ),
            "discovery_or_source_selection_failures": failed_at(
                "search", "source_selection", "fetch", "reduction"
            ),
            "semantic_audit_failures": failed_at("semantic_audit", "admission"),
            "requires_deeper_research": deeper_research,
            "mcp_verifier_candidates": verifier_candidates,
            "browser_tool_candidates": sorted(browser_candidates),
            "failures": failure_details,
        },
    ).resolve()
    return SequentialRunResult(
        completed=tuple(completed),
        failures=tuple(failures),
        summary_path=summary_path,
        pilot_summary_path=pilot_summary_path,
    )
