"""Deterministic buildability and final provenance resolution."""

from __future__ import annotations

from datetime import UTC, datetime

from integration_research.audit import AUDIT_PROMPT_VERSION
from integration_research.extraction import PROMPT_VERSION
from integration_research.models import (
    ApiAvailability,
    ApiCapabilitiesFinal,
    AppInput,
    AppResearchDraft,
    AuthMethod,
    AuthMethodDraft,
    Buildability,
    Claim,
    CredentialAccess,
    EvidenceSnippet,
    FetchedSource,
    FinalAppResearch,
    McpStatus,
    ProductionGate,
    ResolvedAuthMethod,
    ResolvedClaim,
    ResolvedEvidence,
    Ternary,
)


def compute_buildability(draft: AppResearchDraft) -> Buildability:
    available_api = draft.api_availability.value in {
        ApiAvailability.YES,
        ApiAvailability.LIMITED,
    } and bool(draft.api_styles)
    usable_mcp = draft.mcp_status.value == McpStatus.OFFICIAL
    usable_cli = draft.cli.value == Ternary.YES
    usable_surface = available_api or usable_mcp or usable_cli

    if not usable_surface:
        explicitly_absent = (
            draft.api_availability.value == ApiAvailability.NO
            and draft.cli.value == Ternary.NO
            and draft.mcp_status.value == McpStatus.NOT_FOUND
        )
        return Buildability.NO if explicitly_absent else Buildability.UNKNOWN

    if draft.credential_access.value == CredentialAccess.NOT_AVAILABLE:
        return Buildability.NO

    conditional_access = {
        CredentialAccess.ADMIN_REQUIRED,
        CredentialAccess.VENDOR_APPROVAL,
        CredentialAccess.PARTNER_ONLY,
        CredentialAccess.CONTACT_SALES,
    }
    conditional_gates = {
        ProductionGate.APP_REVIEW,
        ProductionGate.ADMIN_APPROVAL,
        ProductionGate.VENDOR_APPROVAL,
        ProductionGate.PARTNER_APPROVAL,
    }
    if (
        draft.credential_access.value in conditional_access
        or draft.production_gate.value in conditional_gates
    ):
        return Buildability.CONDITIONAL
    if draft.blocker is not None:
        return Buildability.CONDITIONAL
    usable_access = draft.credential_access.value in {
        CredentialAccess.SELF_SERVE,
        CredentialAccess.NOT_REQUIRED,
    } or any(item.method == AuthMethod.NONE for item in draft.auth_methods)
    if not usable_access:
        return Buildability.UNKNOWN
    return Buildability.YES


def explain_buildability(draft: AppResearchDraft) -> str:
    verdict = compute_buildability(draft)
    paths = derive_integration_paths(draft)
    if verdict == Buildability.NO:
        return "Evidence explicitly rules out every API, MCP, and CLI execution path."
    if verdict == Buildability.UNKNOWN:
        if not paths:
            return "No callable API, MCP, or CLI execution path was established."
        return (
            "A callable surface exists, but a usable credential or no-auth path was not "
            "established."
        )
    if verdict == Buildability.CONDITIONAL:
        if draft.blocker is not None:
            return (
                "A callable surface exists, but an evidence-backed blocker prevents "
                "unconditional use."
            )
        return (
            "A callable surface exists, but access requires explicit approval, review, or "
            "administration."
        )
    return (
        "A callable surface and a self-serve or no-auth execution path are established without "
        "an explicit blocker."
    )


def derive_integration_paths(draft: AppResearchDraft) -> list[str]:
    paths: set[str] = set()
    if draft.api_availability.value in {ApiAvailability.YES, ApiAvailability.LIMITED}:
        paths.update(claim.value.value for claim in draft.api_styles)
    if draft.mcp_status.value in {McpStatus.OFFICIAL, McpStatus.COMMUNITY}:
        paths.add(f"{draft.mcp_status.value.value}_mcp")
    if draft.cli.value == Ternary.YES:
        paths.add("cli")
    return sorted(paths)


def resolve_claim[ClaimT](
    claim: Claim[ClaimT],
    sources: dict[str, FetchedSource],
    snippets: dict[str, EvidenceSnippet],
) -> ResolvedClaim[ClaimT]:
    evidence = [
        resolve_evidence(reference.source_id, reference.snippet_id, sources, snippets)
        for reference in claim.evidence
    ]
    return ResolvedClaim[ClaimT](value=claim.value, evidence=evidence)


def resolve_evidence(
    source_id: str,
    snippet_id: str,
    sources: dict[str, FetchedSource],
    snippets: dict[str, EvidenceSnippet],
) -> ResolvedEvidence:
    source = sources[source_id]
    snippet = snippets[snippet_id]
    return ResolvedEvidence(
        source_id=source.source_id,
        url=source.url,
        title=source.title,
        source_tier=source.source_tier,
        source_role=source.source_role,
        source_roles=source.source_roles or [source.source_role],
        quote=snippet.text,
        retrieved_at=source.retrieved_at,
        content_hash=source.content_hash,
    )


def resolve_auth(
    item: AuthMethodDraft,
    sources: dict[str, FetchedSource],
    snippets: dict[str, EvidenceSnippet],
) -> ResolvedAuthMethod:
    return ResolvedAuthMethod(
        method=item.method,
        details=item.details,
        evidence=[
            resolve_evidence(ref.source_id, ref.snippet_id, sources, snippets)
            for ref in item.evidence
        ],
    )


def build_final_record(
    *,
    draft: AppResearchDraft,
    app_input: AppInput,
    sources: dict[str, FetchedSource],
    snippets: dict[str, EvidenceSnippet],
    extraction_model: str,
    audit_model: str,
    official_domains: list[str],
) -> FinalAppResearch:
    return FinalAppResearch(
        app_id=draft.app_id,
        app_name=draft.app_name,
        website_hint=app_input.website_hint,
        category=draft.category,
        official_domains=official_domains,
        description=resolve_claim(draft.description, sources, snippets),
        auth_methods=[resolve_auth(item, sources, snippets) for item in draft.auth_methods],
        credential_access=resolve_claim(draft.credential_access, sources, snippets),
        commercial_requirement=resolve_claim(draft.commercial_requirement, sources, snippets),
        production_gate=resolve_claim(draft.production_gate, sources, snippets),
        api_availability=resolve_claim(draft.api_availability, sources, snippets),
        api_styles=[resolve_claim(claim, sources, snippets) for claim in draft.api_styles],
        webhooks=resolve_claim(draft.webhooks, sources, snippets),
        official_sdk=resolve_claim(draft.official_sdk, sources, snippets),
        cli=resolve_claim(draft.cli, sources, snippets),
        api_breadth=resolve_claim(draft.api_breadth, sources, snippets),
        api_capabilities=ApiCapabilitiesFinal(
            read=resolve_claim(draft.api_capabilities.read, sources, snippets),
            write=resolve_claim(draft.api_capabilities.write, sources, snippets),
        ),
        api_surface_summary=resolve_claim(draft.api_surface_summary, sources, snippets),
        mcp_status=resolve_claim(draft.mcp_status, sources, snippets),
        blocker=(
            resolve_claim(draft.blocker, sources, snippets) if draft.blocker is not None else None
        ),
        unresolved_questions=draft.unresolved_questions,
        buildability=compute_buildability(draft),
        integration_paths=derive_integration_paths(draft),
        generated_at=datetime.now(UTC),
        extraction_model=extraction_model,
        audit_model=audit_model,
        pipeline_version="0.1.2-milestone-1.2",
        extraction_prompt_version=PROMPT_VERSION,
        audit_prompt_version=AUDIT_PROMPT_VERSION,
    )
