"""Fatal structural, literal-provenance, and consistency validation."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from integration_research.models import (
    ApiAvailability,
    ApiBreadth,
    AppInput,
    AppResearchDraft,
    AuthMethod,
    CommercialRequirement,
    CredentialAccess,
    EvidenceRef,
    EvidenceSnippet,
    FetchedSource,
    McpStatus,
    ProductionGate,
    SourceTier,
    Ternary,
    ValidationIssue,
    ValidationReport,
)


@dataclass(frozen=True)
class MaterialClaim:
    field: str
    value: object
    evidence: list[EvidenceRef]


def normalize_evidence_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    # Composio returns Markdown. Normalize raw links and bracketed rendered labels to the same
    # visible text. This remains deterministic literal matching; it performs no fuzzy comparison.
    normalized = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", normalized)
    normalized = re.sub(r"\[([^\]]+)\]", r"\1", normalized)
    normalized = normalized.replace("**", "").replace("__", "").replace("`", "")
    return re.sub(r"\s+", " ", normalized).strip()


def quote_exists(quote: str, source_text: str) -> bool:
    return normalize_evidence_text(quote) in normalize_evidence_text(source_text)


def iter_material_claims(draft: AppResearchDraft) -> list[MaterialClaim]:
    claims = [
        MaterialClaim("description", draft.description.value, draft.description.evidence),
        MaterialClaim(
            "credential_access", draft.credential_access.value, draft.credential_access.evidence
        ),
        MaterialClaim(
            "commercial_requirement",
            draft.commercial_requirement.value,
            draft.commercial_requirement.evidence,
        ),
        MaterialClaim(
            "production_gate", draft.production_gate.value, draft.production_gate.evidence
        ),
        MaterialClaim(
            "api_availability", draft.api_availability.value, draft.api_availability.evidence
        ),
        MaterialClaim("webhooks", draft.webhooks.value, draft.webhooks.evidence),
        MaterialClaim("official_sdk", draft.official_sdk.value, draft.official_sdk.evidence),
        MaterialClaim("cli", draft.cli.value, draft.cli.evidence),
        MaterialClaim("api_breadth", draft.api_breadth.value, draft.api_breadth.evidence),
        MaterialClaim(
            "api_capabilities.read",
            draft.api_capabilities.read.value,
            draft.api_capabilities.read.evidence,
        ),
        MaterialClaim(
            "api_capabilities.write",
            draft.api_capabilities.write.value,
            draft.api_capabilities.write.evidence,
        ),
        MaterialClaim(
            "api_surface_summary",
            draft.api_surface_summary.value,
            draft.api_surface_summary.evidence,
        ),
        MaterialClaim("mcp_status", draft.mcp_status.value, draft.mcp_status.evidence),
    ]
    claims.extend(
        MaterialClaim(f"auth_methods[{index}]", item.method, item.evidence)
        for index, item in enumerate(draft.auth_methods)
    )
    claims.extend(
        MaterialClaim(f"api_styles[{index}]", item.value, item.evidence)
        for index, item in enumerate(draft.api_styles)
    )
    if draft.blocker is not None:
        claims.append(MaterialClaim("blocker", draft.blocker.value, draft.blocker.evidence))
    return claims


def is_unknown(value: object) -> bool:
    return value is None or value in {
        AuthMethod.UNKNOWN,
        CredentialAccess.UNKNOWN,
        CommercialRequirement.UNKNOWN,
        ProductionGate.UNKNOWN,
        ApiAvailability.UNKNOWN,
        ApiBreadth.UNKNOWN,
        Ternary.UNKNOWN,
        McpStatus.UNKNOWN,
    }


def _question_covers(field: str, questions: list[str]) -> bool:
    terms = {
        "description": ("description", "what", "product"),
        "auth_methods": ("auth", "token", "credential"),
        "credential_access": ("access", "credential", "create"),
        "commercial_requirement": ("commercial", "free", "paid", "plan", "price"),
        "production_gate": ("production", "approval", "gate", "review"),
        "api_availability": ("api", "interface"),
        "api_styles": ("style", "rest", "graphql", "rpc", "api"),
        "webhooks": ("webhook", "event"),
        "official_sdk": ("sdk", "library"),
        "cli": ("cli", "command line"),
        "api_breadth": ("breadth", "coverage", "surface", "api"),
        "api_capabilities": ("read", "write", "capabil"),
        "api_surface_summary": ("surface", "api", "operation"),
        "mcp_status": ("mcp", "model context protocol"),
        "blocker": ("blocker", "prevent"),
    }
    root = field.split("[", 1)[0].split(".", 1)[0]
    expected = terms.get(root, (root.replace("_", " "),))
    return any(any(term in question.lower() for term in expected) for question in questions)


def normalize_unknown_questions(
    draft: AppResearchDraft,
) -> tuple[AppResearchDraft, list[ValidationIssue]]:
    """Add deterministic review questions for model-returned unknowns.

    The raw draft remains immutable in storage. This normalization only repairs bookkeeping that
    can be derived from the schema; it never upgrades an unknown value or invents evidence.
    """

    normalized = draft.model_copy(deep=True)
    issues: list[ValidationIssue] = []
    unknown_fields = [
        claim.field for claim in iter_material_claims(normalized) if is_unknown(claim.value)
    ]
    if not normalized.api_styles:
        unknown_fields.append("api_styles")
    for field in dict.fromkeys(unknown_fields):
        if _question_covers(field, normalized.unresolved_questions):
            continue
        root = field.split("[", 1)[0].split(".", 1)[0]
        label = root.replace("_", " ")
        normalized.unresolved_questions.append(
            f"What evidence resolves the {label} for {normalized.app_name}?"
        )
        issues.append(
            ValidationIssue(
                level="normalization",
                code="unknown_question_added",
                field=field,
                message="Added the missing deterministic unresolved question.",
            )
        )
    return normalized, issues


def validate_draft(
    draft: AppResearchDraft,
    *,
    app_input: AppInput,
    sources: dict[str, FetchedSource],
    snippets: dict[str, EvidenceSnippet],
    normalizations: list[ValidationIssue] | None = None,
) -> ValidationReport:
    """Validate facts that code can prove without semantic judgment."""

    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    unknown_fields: list[str] = []

    def error(code: str, field: str, message: str) -> None:
        errors.append(ValidationIssue(level="error", code=code, field=field, message=message))

    def warning(code: str, field: str, message: str) -> None:
        warnings.append(ValidationIssue(level="warning", code=code, field=field, message=message))

    if draft.app_id != app_input.app_id:
        error("identity_mismatch", "app_id", "draft app_id does not match apps.csv")
    if draft.app_name != app_input.app_name:
        error("identity_mismatch", "app_name", "draft app_name does not match apps.csv")
    if draft.category != app_input.category:
        error("identity_mismatch", "category", "draft category does not match apps.csv")
    if draft.description.value is not None:
        description = draft.description.value.strip()
        if not description or "\n" in description:
            error("invalid_description", "description", "description must be one non-empty line")

    for field, value, evidence in (
        (claim.field, claim.value, claim.evidence) for claim in iter_material_claims(draft)
    ):
        if is_unknown(value):
            unknown_fields.append(field)
            if evidence:
                warning(
                    "unknown_has_evidence",
                    field,
                    "unknown claim carries evidence that is not admitted",
                )
            if not _question_covers(field, draft.unresolved_questions):
                error(
                    "unknown_without_question",
                    field,
                    "material unknown does not have a matching unresolved question",
                )
            continue
        if isinstance(value, str) and not value.strip():
            error("empty_claim", field, "known text claim must not be empty")
        if not evidence:
            error("missing_evidence", field, "known material claim has no evidence")
            continue
        for index, reference in enumerate(evidence):
            evidence_field = f"{field}.evidence[{index}]"
            source = sources.get(reference.source_id)
            if source is None:
                error("unknown_source", evidence_field, "evidence source_id does not exist")
                continue
            if not source.successful:
                error("failed_source", evidence_field, "evidence references a failed fetch")
                continue
            snippet = snippets.get(reference.snippet_id)
            if snippet is None:
                error("unknown_snippet", evidence_field, "evidence snippet_id does not exist")
                continue
            if snippet.source_id != reference.source_id:
                error(
                    "snippet_source_mismatch",
                    evidence_field,
                    "evidence snippet belongs to a different source",
                )
                continue
            if not quote_exists(snippet.text, source.text):
                error(
                    "quote_not_found",
                    evidence_field,
                    "evidence snippet does not occur in the fetched source",
                )

    if not draft.api_styles:
        unknown_fields.append("api_styles")
        if not _question_covers("api_styles", draft.unresolved_questions):
            error(
                "unknown_without_question",
                "api_styles",
                "empty API styles require a matching unresolved question",
            )

    availability = draft.api_availability.value
    if availability == ApiAvailability.NO:
        if draft.api_styles:
            error("api_contradiction", "api_styles", "absent API cannot expose API styles")
        if draft.api_breadth.value != ApiBreadth.NONE:
            error("api_contradiction", "api_breadth", "absent API requires breadth none")
        if Ternary.YES in {
            draft.api_capabilities.read.value,
            draft.api_capabilities.write.value,
        }:
            error("api_contradiction", "api_capabilities", "absent API cannot read or write")
    if availability in {ApiAvailability.YES, ApiAvailability.LIMITED}:
        if not draft.api_styles:
            warning(
                "api_style_unknown",
                "api_styles",
                "available API has no semantically admitted style",
            )
        if draft.api_breadth.value == ApiBreadth.NONE:
            error("api_contradiction", "api_breadth", "available API cannot have breadth none")
        if (
            draft.api_capabilities.read.value == Ternary.NO
            and draft.api_capabilities.write.value == Ternary.NO
        ):
            error(
                "api_capability_missing",
                "api_capabilities",
                "available API cannot have both read and write explicitly absent",
            )
    if draft.api_breadth.value == ApiBreadth.NONE and draft.api_styles:
        error("api_contradiction", "api_breadth", "API styles cannot coexist with breadth none")

    if draft.mcp_status.value == McpStatus.OFFICIAL:
        for reference in draft.mcp_status.evidence:
            source = sources.get(reference.source_id)
            if source is None or not source.successful:
                continue
            if source.source_tier not in set(SourceTier):
                error("mcp_not_official", "mcp_status", "official MCP lacks official evidence")

    return ValidationReport(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        normalizations=normalizations or [],
        unknown_fields=sorted(set(unknown_fields)),
    )
