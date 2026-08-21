"""Deterministic evidence and semantic validation."""

from __future__ import annotations

import re
import unicodedata
from typing import cast

from integration_research.models import (
    ApiAvailability,
    ApiBreadth,
    ApiProtocol,
    AppInput,
    AppResearchDraft,
    AuthMethod,
    Claim,
    DeveloperAccess,
    FetchedSource,
    McpStatus,
    ProductionGate,
    Ternary,
    ValidationIssue,
    ValidationReport,
)

NEGATIVE_MARKERS: tuple[str, ...] = (
    "no api",
    "does not provide",
    "does not support",
    "not supported",
    "not available",
    "unavailable",
    "deprecated",
    "discontinued",
)


def normalize_evidence_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip()


def quote_exists(quote: str, source_text: str) -> bool:
    return normalize_evidence_text(quote) in normalize_evidence_text(source_text)


def _has_explicit_negative(claim: Claim[object], sources: dict[str, FetchedSource]) -> bool:
    for evidence in claim.evidence:
        source = sources.get(evidence.source_id)
        quote = normalize_evidence_text(evidence.quote).lower()
        if (
            source is not None
            and source.successful
            and any(marker in quote for marker in NEGATIVE_MARKERS)
        ):
            return True
    return False


def normalize_unsupported_negatives(
    draft: AppResearchDraft, sources: dict[str, FetchedSource]
) -> tuple[AppResearchDraft, list[ValidationIssue]]:
    """Convert unsupported negative conclusions to honest unknowns."""

    normalized = draft.model_copy(deep=True)
    changes: list[ValidationIssue] = []

    if normalized.mcp_status.value == McpStatus.NOT_FOUND:
        normalized.mcp_status = Claim[McpStatus](value=McpStatus.UNKNOWN, evidence=[])
        if not any("mcp" in question.lower() for question in normalized.unresolved_questions):
            normalized.unresolved_questions.append(
                "Does GitHub currently provide an official or community MCP server?"
            )
        changes.append(
            ValidationIssue(
                level="warning",
                code="negative_mcp_normalized",
                field="mcp_status",
                message="not_found was normalized to unknown because search absence is not proof",
            )
        )

    api_claim = cast(Claim[object], normalized.api_availability)
    if normalized.api_availability.value == ApiAvailability.NO and not _has_explicit_negative(
        api_claim, sources
    ):
        normalized.api_availability = Claim[ApiAvailability](
            value=ApiAvailability.UNKNOWN, evidence=[]
        )
        if not any("api" in question.lower() for question in normalized.unresolved_questions):
            normalized.unresolved_questions.append("Does GitHub expose a supported developer API?")
        changes.append(
            ValidationIssue(
                level="warning",
                code="negative_api_normalized",
                field="api_availability",
                message="unsupported API absence was normalized to unknown",
            )
        )

    access_claim = cast(Claim[object], normalized.developer_access)
    if normalized.developer_access.value == DeveloperAccess.NOT_AVAILABLE and not (
        _has_explicit_negative(access_claim, sources)
    ):
        normalized.developer_access = Claim[DeveloperAccess](
            value=DeveloperAccess.UNKNOWN, evidence=[]
        )
        if not any(
            "access" in question.lower() or "credential" in question.lower()
            for question in normalized.unresolved_questions
        ):
            normalized.unresolved_questions.append(
                "Can a GitHub developer obtain credentials for the documented interface?"
            )
        changes.append(
            ValidationIssue(
                level="warning",
                code="negative_access_normalized",
                field="developer_access",
                message="unsupported access absence was normalized to unknown",
            )
        )
    return normalized, changes


def _all_claims(draft: AppResearchDraft) -> list[tuple[str, Claim[object]]]:
    claims: list[tuple[str, Claim[object]]] = [
        ("description", cast(Claim[object], draft.description)),
        ("developer_access", cast(Claim[object], draft.developer_access)),
        ("api_availability", cast(Claim[object], draft.api_availability)),
        ("api_breadth", cast(Claim[object], draft.api_breadth)),
        ("api_capabilities.read", cast(Claim[object], draft.api_capabilities.read)),
        ("api_capabilities.write", cast(Claim[object], draft.api_capabilities.write)),
        (
            "api_capabilities.webhooks_or_events",
            cast(Claim[object], draft.api_capabilities.webhooks_or_events),
        ),
        ("api_surface_summary", cast(Claim[object], draft.api_surface_summary)),
        ("mcp_status", cast(Claim[object], draft.mcp_status)),
    ]
    claims.extend(
        (f"auth_methods[{index}]", cast(Claim[object], claim))
        for index, claim in enumerate(draft.auth_methods)
    )
    claims.extend(
        (f"production_gates[{index}]", cast(Claim[object], claim))
        for index, claim in enumerate(draft.production_gates)
    )
    claims.extend(
        (f"api_protocols[{index}]", cast(Claim[object], claim))
        for index, claim in enumerate(draft.api_protocols)
    )
    if draft.blocker is not None:
        claims.append(("blocker", cast(Claim[object], draft.blocker)))
    return claims


def _is_unknown(value: object) -> bool:
    return value in {
        AuthMethod.UNKNOWN,
        DeveloperAccess.UNKNOWN,
        ProductionGate.UNKNOWN,
        ApiAvailability.UNKNOWN,
        ApiProtocol.UNKNOWN,
        ApiBreadth.UNKNOWN,
        Ternary.UNKNOWN,
        McpStatus.UNKNOWN,
    }


def _question_covers(field: str, questions: list[str]) -> bool:
    terms = {
        "auth_methods": ("auth", "token", "credential"),
        "developer_access": ("access", "credential"),
        "production_gates": ("production", "approval", "gate", "review"),
        "api_availability": ("api", "interface"),
        "api_protocols": ("protocol", "rest", "graphql", "api"),
        "api_breadth": ("breadth", "coverage", "surface", "api"),
        "api_capabilities": ("read", "write", "webhook", "event", "capabil"),
        "mcp_status": ("mcp", "model context protocol"),
    }
    root = field.split("[", 1)[0].split(".", 1)[0]
    expected = terms.get(root, (root.replace("_", " "),))
    return any(any(term in question.lower() for term in expected) for question in questions)


def validate_draft(
    draft: AppResearchDraft,
    *,
    app_input: AppInput,
    sources: dict[str, FetchedSource],
    normalizations: list[ValidationIssue] | None = None,
) -> ValidationReport:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    unknown_fields: list[str] = []

    def error(code: str, field: str, message: str) -> None:
        errors.append(ValidationIssue(level="error", code=code, field=field, message=message))

    if draft.app_id != app_input.app_id:
        error("identity_mismatch", "app_id", "draft app_id does not match apps.csv")
    if draft.app_name != app_input.app_name:
        error("identity_mismatch", "app_name", "draft app_name does not match apps.csv")
    if draft.category != app_input.category:
        error("identity_mismatch", "category", "draft category does not match apps.csv")
    if not draft.description.value.strip() or "\n" in draft.description.value.strip():
        error("invalid_description", "description", "description must be one non-empty line")

    for field, claim in _all_claims(draft):
        if _is_unknown(claim.value):
            unknown_fields.append(field)
            if claim.evidence:
                warnings.append(
                    ValidationIssue(
                        level="warning",
                        code="unknown_has_evidence",
                        field=field,
                        message="unknown claim carries evidence that is not needed",
                    )
                )
            if not _question_covers(field, draft.unresolved_questions):
                error(
                    "unknown_without_question",
                    field,
                    "material unknown does not have a matching unresolved question",
                )
            continue
        if isinstance(claim.value, str) and not claim.value.strip():
            error("empty_claim", field, "known text claim must not be empty")
        if not claim.evidence:
            error("missing_evidence", field, "known material claim has no evidence")
            continue
        for index, evidence in enumerate(claim.evidence):
            evidence_field = f"{field}.evidence[{index}]"
            source = sources.get(evidence.source_id)
            if source is None:
                error("unknown_source", evidence_field, "evidence source_id does not exist")
                continue
            if not source.successful:
                error("failed_source", evidence_field, "evidence references a failed fetch")
                continue
            if not quote_exists(evidence.quote, source.text):
                error(
                    "quote_not_found",
                    evidence_field,
                    "evidence quote does not occur in the fetched source",
                )

    availability = draft.api_availability.value
    protocol_values = [claim.value for claim in draft.api_protocols]
    if availability == ApiAvailability.NO:
        if protocol_values:
            error("api_contradiction", "api_protocols", "absent API cannot expose protocols")
        if draft.api_breadth.value != ApiBreadth.NONE:
            error("api_contradiction", "api_breadth", "absent API requires breadth none")
        capability_values = {
            draft.api_capabilities.read.value,
            draft.api_capabilities.write.value,
            draft.api_capabilities.webhooks_or_events.value,
        }
        if Ternary.YES in capability_values:
            error("api_contradiction", "api_capabilities", "absent API cannot have capabilities")
    if availability in {ApiAvailability.YES, ApiAvailability.LIMITED}:
        confirmed_protocols = [value for value in protocol_values if value != ApiProtocol.UNKNOWN]
        if not confirmed_protocols:
            error("api_protocol_missing", "api_protocols", "available API needs a protocol")
        if draft.api_breadth.value == ApiBreadth.NONE:
            error("api_contradiction", "api_breadth", "available API cannot have breadth none")
        if (
            draft.api_capabilities.read.value != Ternary.YES
            and draft.api_capabilities.write.value != Ternary.YES
        ):
            error(
                "api_capability_missing",
                "api_capabilities",
                "available API needs a meaningful read or write capability",
            )

    if draft.mcp_status.value == McpStatus.OFFICIAL:
        for evidence in draft.mcp_status.evidence:
            source = sources.get(evidence.source_id)
            if source is None or not source.successful:
                continue
            if source.source_tier.value not in {
                "official_developer_docs",
                "official_github",
                "official_blog",
            }:
                error("mcp_not_official", "mcp_status", "official MCP lacks official evidence")

    return ValidationReport(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        normalizations=normalizations or [],
        unknown_fields=sorted(set(unknown_fields)),
    )
