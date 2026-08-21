"""Shared deterministic fixtures for Milestone 1 tests."""

from __future__ import annotations

from datetime import UTC, datetime

from integration_research.models import (
    ApiAvailability,
    ApiBreadth,
    ApiCapabilitiesDraft,
    ApiProtocol,
    AppInput,
    AppResearchDraft,
    AuthMethod,
    Claim,
    DeveloperAccess,
    EvidenceRef,
    FetchedSource,
    McpStatus,
    ProductionGate,
    SourceTier,
    Ternary,
)

AUTH_QUOTE = "GitHub accepts a personal access token in the Authorization header."
ACCESS_QUOTE = "You can create credentials without vendor review."
API_QUOTE = "The REST and GraphQL APIs support repository read and write operations and webhooks."


def evidence(source_id: str, quote: str) -> list[EvidenceRef]:
    return [EvidenceRef(source_id=source_id, quote=quote)]


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
            "https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api",
            "Authentication",
            AUTH_QUOTE,
            SourceTier.OFFICIAL_DEVELOPER_DOCS,
        ),
        (
            "source_2",
            "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens",
            "Credentials",
            ACCESS_QUOTE,
            SourceTier.OFFICIAL_DEVELOPER_DOCS,
        ),
        (
            "source_3",
            "https://docs.github.com/en/rest/about-the-rest-api/about-the-rest-api",
            "API surface",
            API_QUOTE,
            SourceTier.OFFICIAL_DEVELOPER_DOCS,
        ),
        (
            "source_4",
            "https://github.com/github/github-mcp-server",
            "GitHub repository",
            "This repository contains integration software.",
            SourceTier.OFFICIAL_GITHUB,
        ),
    )
    return {
        source_id: FetchedSource(
            source_id=source_id,
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
        for source_id, url, title, text, tier in values
    }


def make_valid_draft() -> AppResearchDraft:
    api_evidence = evidence("source_3", API_QUOTE)
    return AppResearchDraft(
        app_id=61,
        app_name="GitHub",
        category="Developer, Infra and Data platforms",
        description=Claim[str](
            value="GitHub is a developer platform with repository APIs.",
            evidence=evidence("source_3", API_QUOTE),
        ),
        auth_methods=[
            Claim[AuthMethod](
                value=AuthMethod.PERSONAL_ACCESS_TOKEN,
                evidence=evidence("source_1", AUTH_QUOTE),
            )
        ],
        developer_access=Claim[DeveloperAccess](
            value=DeveloperAccess.SELF_SERVE_FREE,
            evidence=evidence("source_2", ACCESS_QUOTE),
        ),
        production_gates=[
            Claim[ProductionGate](
                value=ProductionGate.NONE,
                evidence=evidence("source_2", ACCESS_QUOTE),
            )
        ],
        api_availability=Claim[ApiAvailability](value=ApiAvailability.YES, evidence=api_evidence),
        api_protocols=[
            Claim[ApiProtocol](value=ApiProtocol.REST, evidence=api_evidence),
            Claim[ApiProtocol](value=ApiProtocol.GRAPHQL, evidence=api_evidence),
        ],
        api_breadth=Claim[ApiBreadth](value=ApiBreadth.BROAD, evidence=api_evidence),
        api_capabilities=ApiCapabilitiesDraft(
            read=Claim[Ternary](value=Ternary.YES, evidence=api_evidence),
            write=Claim[Ternary](value=Ternary.YES, evidence=api_evidence),
            webhooks_or_events=Claim[Ternary](value=Ternary.YES, evidence=api_evidence),
        ),
        api_surface_summary=Claim[str](
            value="Repository read and write APIs with webhook support.", evidence=api_evidence
        ),
        mcp_status=Claim[McpStatus](value=McpStatus.UNKNOWN, evidence=[]),
        blocker=None,
        unresolved_questions=["Does GitHub provide an official MCP server?"],
    )
