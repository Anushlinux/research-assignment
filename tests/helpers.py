"""Shared deterministic fixtures for Milestone 1.1 tests."""

from __future__ import annotations

from datetime import UTC, datetime

from integration_research.models import (
    ApiAvailability,
    ApiBreadth,
    ApiCapabilitiesDraft,
    ApiStyle,
    AppInput,
    AppResearchDraft,
    AuthMethod,
    AuthMethodDraft,
    Claim,
    CommercialRequirement,
    CredentialAccess,
    EvidenceRef,
    EvidenceSnippet,
    FetchedSource,
    McpStatus,
    ProductionGate,
    SourceRole,
    SourceTier,
    Ternary,
)

AUTH_QUOTE = "GitHub accepts a personal access token in the Authorization header."
ACCESS_QUOTE = "You can create credentials without vendor review."
COMMERCIAL_QUOTE = "A free GitHub account can use personal access tokens."
GATE_QUOTE = "No app review or production approval is required for personal access tokens."
API_QUOTE = "The REST and GraphQL APIs support repository read and write operations and webhooks."
SDK_QUOTE = "GitHub provides the official Octokit client libraries for its API."
CLI_QUOTE = "The GitHub CLI api command makes authenticated API requests."
MCP_QUOTE = "This is GitHub's official MCP server."


def evidence(source_id: str, quote: str) -> list[EvidenceRef]:
    del quote
    return [EvidenceRef(source_id=source_id, snippet_id=f"{source_id}_snippet_001")]


def make_app_input() -> AppInput:
    return AppInput(
        app_id=61,
        app_name="GitHub",
        website_hint="docs.github.com/rest",
        category="Developer, Infra and Data platforms",
        notes="",
    )


def make_sources() -> dict[str, FetchedSource]:
    values = (
        (
            "source_1",
            SourceRole.AUTHENTICATION,
            "https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api",
            "Authentication",
            AUTH_QUOTE,
            SourceTier.OFFICIAL_DEVELOPER_DOCS,
        ),
        (
            "source_2",
            SourceRole.CREDENTIAL_ACCESS,
            "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens",
            "Credentials",
            ACCESS_QUOTE,
            SourceTier.OFFICIAL_DEVELOPER_DOCS,
        ),
        (
            "source_3",
            SourceRole.API_SURFACE,
            "https://docs.github.com/en/rest/about-the-rest-api/about-the-rest-api",
            "API surface",
            " ".join((API_QUOTE, SDK_QUOTE, CLI_QUOTE)),
            SourceTier.OFFICIAL_DEVELOPER_DOCS,
        ),
        (
            "source_4",
            SourceRole.COMMERCIAL_OR_PRODUCTION_GATE,
            "https://docs.github.com/en/get-started/learning-about-github/types-of-github-accounts",
            "Production approval pricing",
            " ".join((COMMERCIAL_QUOTE, GATE_QUOTE)),
            SourceTier.OFFICIAL_DEVELOPER_DOCS,
        ),
        (
            "source_5",
            SourceRole.MCP,
            "https://docs.github.com/mcp/server",
            "MCP Server",
            MCP_QUOTE,
            SourceTier.OFFICIAL_DEVELOPER_DOCS,
        ),
    )
    return {
        source_id: FetchedSource(
            source_id=source_id,
            source_role=role,
            url=url,
            title=title,
            source_tier=tier,
            text=text,
            successful=True,
            retrieved_at=datetime(2026, 8, 21, tzinfo=UTC),
            content_hash=f"hash-{source_id}",
            log_id=f"log-{source_id}",
            raw_response={"data": {"results": []}},
            latency_ms=1,
        )
        for source_id, role, url, title, text, tier in values
    }


def make_snippets() -> dict[str, EvidenceSnippet]:
    sources = make_sources()
    return {
        f"{source_id}_snippet_001": EvidenceSnippet(
            snippet_id=f"{source_id}_snippet_001",
            source_id=source_id,
            text=source.text,
        )
        for source_id, source in sources.items()
    }


def make_valid_draft() -> AppResearchDraft:
    api_evidence = evidence("source_3", API_QUOTE)
    return AppResearchDraft(
        app_id=61,
        app_name="GitHub",
        category="Developer, Infra and Data platforms",
        description=Claim[str | None](
            value="GitHub is a developer platform with repository APIs.",
            evidence=api_evidence,
        ),
        auth_methods=[
            AuthMethodDraft(
                method=AuthMethod.TOKEN,
                details="GitHub personal access token",
                evidence=evidence("source_1", AUTH_QUOTE),
            )
        ],
        credential_access=Claim[CredentialAccess](
            value=CredentialAccess.SELF_SERVE,
            evidence=evidence("source_2", ACCESS_QUOTE),
        ),
        commercial_requirement=Claim[CommercialRequirement](
            value=CommercialRequirement.FREE_AVAILABLE,
            evidence=evidence("source_4", COMMERCIAL_QUOTE),
        ),
        production_gate=Claim[ProductionGate](
            value=ProductionGate.NONE,
            evidence=evidence("source_4", GATE_QUOTE),
        ),
        api_availability=Claim[ApiAvailability](value=ApiAvailability.YES, evidence=api_evidence),
        api_styles=[
            Claim[ApiStyle](value=ApiStyle.REST, evidence=api_evidence),
            Claim[ApiStyle](value=ApiStyle.GRAPHQL, evidence=api_evidence),
        ],
        webhooks=Claim[Ternary](value=Ternary.YES, evidence=api_evidence),
        official_sdk=Claim[Ternary](value=Ternary.YES, evidence=evidence("source_3", SDK_QUOTE)),
        cli=Claim[Ternary](value=Ternary.YES, evidence=evidence("source_3", CLI_QUOTE)),
        api_breadth=Claim[ApiBreadth](value=ApiBreadth.BROAD, evidence=api_evidence),
        api_capabilities=ApiCapabilitiesDraft(
            read=Claim[Ternary](value=Ternary.YES, evidence=api_evidence),
            write=Claim[Ternary](value=Ternary.YES, evidence=api_evidence),
        ),
        api_surface_summary=Claim[str | None](
            value="Repository read and write APIs with webhook support.", evidence=api_evidence
        ),
        mcp_status=Claim[McpStatus](
            value=McpStatus.OFFICIAL, evidence=evidence("source_5", MCP_QUOTE)
        ),
        blocker=None,
        unresolved_questions=[],
    )
