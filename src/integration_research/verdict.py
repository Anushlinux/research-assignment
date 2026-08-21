"""Deterministic buildability and final provenance resolution."""

from __future__ import annotations

from datetime import UTC, datetime

from integration_research.extraction import PROMPT_VERSION
from integration_research.models import (
    ApiAvailability,
    ApiBreadth,
    ApiCapabilitiesFinal,
    ApiProtocol,
    AppInput,
    AppResearchDraft,
    Buildability,
    Claim,
    DeveloperAccess,
    FetchedSource,
    FinalAppResearch,
    McpStatus,
    ProductionGate,
    ResolvedClaim,
    ResolvedEvidence,
    Ternary,
)


def compute_buildability(draft: AppResearchDraft) -> Buildability:
    available_api = draft.api_availability.value in {
        ApiAvailability.YES,
        ApiAvailability.LIMITED,
    }
    available_mcp = draft.mcp_status.value in {McpStatus.OFFICIAL, McpStatus.COMMUNITY}
    available_cli = any(claim.value == ApiProtocol.CLI for claim in draft.api_protocols)
    usable_surface = available_api or available_mcp or available_cli

    if not usable_surface:
        if (
            draft.api_availability.value == ApiAvailability.NO
            or draft.developer_access.value == DeveloperAccess.NOT_AVAILABLE
        ):
            return Buildability.NO
        return Buildability.UNKNOWN

    material_unknowns = {
        draft.developer_access.value == DeveloperAccess.UNKNOWN,
        draft.api_availability.value == ApiAvailability.UNKNOWN
        and not (available_mcp or available_cli),
        draft.api_breadth.value == ApiBreadth.UNKNOWN and available_api,
        draft.api_capabilities.read.value == Ternary.UNKNOWN and available_api,
        draft.api_capabilities.write.value == Ternary.UNKNOWN and available_api,
    }
    if True in material_unknowns:
        return Buildability.UNKNOWN

    conditional_access = {
        DeveloperAccess.SELF_SERVE_PAID,
        DeveloperAccess.ADMIN_REQUIRED,
        DeveloperAccess.VENDOR_REVIEW,
        DeveloperAccess.PARTNER_ONLY,
        DeveloperAccess.CONTACT_SALES,
    }
    gates = {claim.value for claim in draft.production_gates}
    conditional_gates = {
        ProductionGate.PAID_PLAN,
        ProductionGate.APP_REVIEW,
        ProductionGate.ADMIN_APPROVAL,
        ProductionGate.VENDOR_APPROVAL,
        ProductionGate.PARTNER_APPROVAL,
        ProductionGate.CONTACT_SALES,
        ProductionGate.CUSTOMER_ACCOUNT_REQUIRED,
    }
    if draft.developer_access.value in conditional_access or gates & conditional_gates:
        return Buildability.CONDITIONAL
    if draft.api_availability.value == ApiAvailability.LIMITED:
        return Buildability.CONDITIONAL
    if draft.api_breadth.value == ApiBreadth.NARROW:
        return Buildability.CONDITIONAL
    if draft.api_capabilities.write.value == Ternary.NO:
        return Buildability.CONDITIONAL
    return Buildability.YES


def derive_integration_paths(draft: AppResearchDraft) -> list[str]:
    paths = {
        claim.value.value for claim in draft.api_protocols if claim.value != ApiProtocol.UNKNOWN
    }
    if draft.mcp_status.value in {McpStatus.OFFICIAL, McpStatus.COMMUNITY}:
        paths.add("mcp")
    return sorted(paths)


def resolve_claim[ClaimT](
    claim: Claim[ClaimT], sources: dict[str, FetchedSource]
) -> ResolvedClaim[ClaimT]:
    evidence = [
        ResolvedEvidence(
            source_id=reference.source_id,
            url=sources[reference.source_id].url,
            title=sources[reference.source_id].title,
            source_tier=sources[reference.source_id].source_tier,
            quote=reference.quote,
            retrieved_at=sources[reference.source_id].retrieved_at,
            content_hash=sources[reference.source_id].content_hash,
        )
        for reference in claim.evidence
    ]
    return ResolvedClaim[ClaimT](value=claim.value, evidence=evidence)


def build_final_record(
    *, draft: AppResearchDraft, app_input: AppInput, sources: dict[str, FetchedSource], model: str
) -> FinalAppResearch:
    return FinalAppResearch(
        app_id=draft.app_id,
        app_name=draft.app_name,
        website_hint=app_input.website_hint,
        category=draft.category,
        official_domains=["docs.github.com", "github.blog", "github.com/github/*"],
        description=resolve_claim(draft.description, sources),
        auth_methods=[resolve_claim(claim, sources) for claim in draft.auth_methods],
        developer_access=resolve_claim(draft.developer_access, sources),
        production_gates=[resolve_claim(claim, sources) for claim in draft.production_gates],
        api_availability=resolve_claim(draft.api_availability, sources),
        api_protocols=[resolve_claim(claim, sources) for claim in draft.api_protocols],
        api_breadth=resolve_claim(draft.api_breadth, sources),
        api_capabilities=ApiCapabilitiesFinal(
            read=resolve_claim(draft.api_capabilities.read, sources),
            write=resolve_claim(draft.api_capabilities.write, sources),
            webhooks_or_events=resolve_claim(draft.api_capabilities.webhooks_or_events, sources),
        ),
        api_surface_summary=resolve_claim(draft.api_surface_summary, sources),
        mcp_status=resolve_claim(draft.mcp_status, sources),
        blocker=resolve_claim(draft.blocker, sources) if draft.blocker is not None else None,
        unresolved_questions=draft.unresolved_questions,
        buildability=compute_buildability(draft),
        integration_paths=derive_integration_paths(draft),
        generated_at=datetime.now(UTC),
        model=model,
        pipeline_version="0.1.0-milestone-1",
        prompt_version=PROMPT_VERSION,
    )
