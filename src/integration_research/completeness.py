"""Deterministic source-quality, taxonomy, and research-completeness gates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from integration_research.models import (
    ApiAvailability,
    ApiBreadth,
    AppResearchDraft,
    AuthMethod,
    CompletenessReport,
    CredentialAccess,
    FetchedSource,
    McpStatus,
    SourceRole,
    Ternary,
)

CRITICAL_FIELDS = frozenset(
    {
        "auth_methods",
        "credential_access",
        "api_availability",
        "callable_interface",
        "api_breadth",
        "buildability_path",
    }
)

CRITICAL_ROLES: tuple[SourceRole, ...] = (
    SourceRole.AUTHENTICATION,
    SourceRole.CREDENTIAL_ACCESS,
    SourceRole.API_SURFACE,
)

ROLE_SIGNALS: dict[SourceRole, frozenset[str]] = {
    SourceRole.AUTHENTICATION: frozenset(
        {
            "oauth",
            "authorization code",
            "client id",
            "client secret",
            "api key",
            "access token",
            "authorization header",
            "basic authentication",
        }
    ),
    SourceRole.CREDENTIAL_ACCESS: frozenset(
        {
            "create api key",
            "api keys",
            "credentials",
            "generate token",
            "developer portal",
            "developer settings",
            "workspace settings",
            "register an app",
            "request access",
            "contact sales",
            "admin",
            "administrator",
            "partner",
        }
    ),
    SourceRole.API_SURFACE: frozenset(
        {
            "endpoint",
            "request",
            "response",
            "get",
            "post",
            "patch",
            "delete",
            "rest",
            "graphql",
            "api reference",
            "resource",
            "webhook",
        }
    ),
}

MINIMUM_SIGNAL_HITS: dict[SourceRole, int] = {
    SourceRole.AUTHENTICATION: 2,
    SourceRole.CREDENTIAL_ACCESS: 2,
    SourceRole.API_SURFACE: 3,
}


@dataclass(frozen=True)
class SourceQuality:
    sufficient: bool
    signal_hits: tuple[str, ...]
    generic_homepage: bool
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "sufficient": self.sufficient,
            "signal_hits": list(self.signal_hits),
            "generic_homepage": self.generic_homepage,
            "reason": self.reason,
        }


def assess_source_quality(*, role: SourceRole, url: str, text: str) -> SourceQuality:
    """Require actual developer-interface signals, not only a promising URL or title."""

    if role not in ROLE_SIGNALS:
        raise ValueError(f"Source quality is not defined for role: {role.value}")
    normalized = " ".join(text.lower().split())

    def contains(signal: str) -> bool:
        if signal in {"get", "post", "patch", "delete"}:
            return re.search(rf"\b{signal}\b", normalized) is not None
        return signal in normalized

    hits = tuple(sorted(signal for signal in ROLE_SIGNALS[role] if contains(signal)))
    generic_homepage = urlsplit(url).path.rstrip("/") == ""
    sufficient = len(hits) >= MINIMUM_SIGNAL_HITS[role]
    if generic_homepage and not sufficient:
        reason = "Generic homepage lacks sufficient developer-interface evidence."
    elif sufficient:
        reason = "Contains relevant developer-interface evidence."
    else:
        reason = "Insufficient role-specific developer-interface evidence."
    return SourceQuality(
        sufficient=sufficient,
        signal_hits=hits,
        generic_homepage=generic_homepage,
        reason=reason,
    )


def auth_taxonomy_warnings(draft: AppResearchDraft, sources: dict[str, FetchedSource]) -> list[str]:
    """Flag strong evidence that conflicts with the selected auth enum.

    The function only routes a field to verification. It never rewrites a model value.
    """

    warnings: list[str] = []
    for auth in draft.auth_methods:
        auth_sources = [
            sources[reference.source_id]
            for reference in auth.evidence
            if reference.source_id in sources
        ]
        evidence_text = " ".join(source.text for source in auth_sources).lower()
        details = (auth.details or "").lower()
        oauth_signals = (
            ("authorization code" in evidence_text or "authorization_code" in evidence_text)
            and "client id" in evidence_text
            and "client secret" in evidence_text
        )
        dedicated_oauth_source = any("/oauth" in source.url.lower() for source in auth_sources)

        if auth.method == AuthMethod.OTHER and oauth_signals and dedicated_oauth_source:
            warnings.append(
                "Authentication is classified as other, but dedicated official OAuth "
                "documentation supports oauth2."
            )
        if auth.method == AuthMethod.TOKEN and "oauth" in details and "bearer" in details:
            warnings.append(
                "Bearer transport may have been incorrectly classified as a separate token "
                "authentication method."
            )

        product_login = any(
            signal in evidence_text
            for signal in (
                "sign in with google",
                "email login",
                "employee sso",
                "saml login",
                "normal product login",
            )
        )
        developer_auth = any(
            signal in evidence_text
            for signal in ("api", "oauth", "access token", "authorization header")
        )
        if product_login and not developer_auth and "local" not in details:
            warnings.append(
                "Product login evidence cannot establish developer-interface authentication."
            )
    return list(dict.fromkeys(warnings))


def _critical_unknown_fields(draft: AppResearchDraft) -> list[str]:
    unknown: list[str] = []
    if [item.method for item in draft.auth_methods] == [AuthMethod.UNKNOWN]:
        unknown.append("auth_methods")
    if draft.credential_access.value == CredentialAccess.UNKNOWN:
        unknown.append("credential_access")
    if draft.api_availability.value == ApiAvailability.UNKNOWN:
        unknown.append("api_availability")
    if (
        draft.api_availability.value in {ApiAvailability.YES, ApiAvailability.LIMITED}
        and not draft.api_styles
    ):
        unknown.append("callable_interface")
    if (
        draft.api_availability.value in {ApiAvailability.YES, ApiAvailability.LIMITED}
        and draft.api_breadth.value == ApiBreadth.UNKNOWN
    ):
        unknown.append("api_breadth")

    has_buildability_path = (
        (
            draft.api_availability.value in {ApiAvailability.YES, ApiAvailability.LIMITED}
            and bool(draft.api_styles)
        )
        or draft.cli.value == Ternary.YES
        or draft.mcp_status.value in {McpStatus.OFFICIAL, McpStatus.COMMUNITY}
    )
    if not has_buildability_path and draft.api_availability.value != ApiAvailability.NO:
        unknown.append("buildability_path")
    return unknown


def assess_completeness(
    draft: AppResearchDraft,
    sources: dict[str, FetchedSource],
    *,
    taxonomy_warnings: list[str] | None = None,
) -> CompletenessReport:
    """Keep structural validity separate from evidence and research completeness."""

    critical_unknowns = _critical_unknown_fields(draft)
    if taxonomy_warnings and "auth_methods" not in critical_unknowns:
        critical_unknowns.append("auth_methods")

    weak_roles: list[str] = []
    homepage_only: list[str] = []
    for role in CRITICAL_ROLES:
        role_sources = [
            source
            for source in sources.values()
            if role in (source.source_roles or [source.source_role])
        ]
        qualities = [
            assess_source_quality(role=role, url=source.url, text=source.text)
            for source in role_sources
        ]
        resolved_local_path = (
            role == SourceRole.AUTHENTICATION
            and [item.method for item in draft.auth_methods] == [AuthMethod.NONE]
            and draft.cli.value == Ternary.YES
        ) or (
            role == SourceRole.CREDENTIAL_ACCESS
            and draft.credential_access.value == CredentialAccess.NOT_REQUIRED
            and draft.cli.value == Ternary.YES
        )
        resolved_callable_path = (
            role == SourceRole.API_SURFACE
            and draft.cli.value == Ternary.YES
            and (
                bool(draft.api_styles)
                or draft.api_availability.value in {ApiAvailability.YES, ApiAvailability.LIMITED}
            )
        )
        if not any(quality.sufficient for quality in qualities) and not (
            resolved_local_path or resolved_callable_path
        ):
            weak_roles.append(role.value)
        if qualities and all(quality.generic_homepage for quality in qualities):
            homepage_only.append(role.value)

    eligible = not critical_unknowns and not weak_roles and not homepage_only
    return CompletenessReport(
        critical_unknown_fields=critical_unknowns,
        weak_source_roles=weak_roles,
        generic_homepage_only_roles=homepage_only,
        requires_verification=not eligible,
        eligible_for_final_export=eligible,
    )


def disputed_fields_for_recovery(report: CompletenessReport, *, limit: int) -> list[str]:
    """Turn missing fields and weak roles into at most ``limit`` targeted checks."""

    fields = list(report.critical_unknown_fields)
    role_defaults = {
        SourceRole.AUTHENTICATION.value: "auth_methods",
        SourceRole.CREDENTIAL_ACCESS.value: "credential_access",
        SourceRole.API_SURFACE.value: "api_availability",
    }
    fields.extend(role_defaults[role] for role in report.weak_source_roles)
    return list(dict.fromkeys(fields))[:limit]


def merge_disputed_fields(
    first_pass: AppResearchDraft,
    recovery: AppResearchDraft,
    disputed_fields: list[str],
) -> AppResearchDraft:
    """Admit recovery-pass changes only inside the explicitly disputed field set."""

    merged = first_pass.model_copy(deep=True)
    disputed = set(disputed_fields)
    recovery_auth_unknown = [item.method for item in recovery.auth_methods] == [AuthMethod.UNKNOWN]
    first_auth_known = [item.method for item in first_pass.auth_methods] != [AuthMethod.UNKNOWN]
    if "auth_methods" in disputed and not (recovery_auth_unknown and first_auth_known):
        merged.auth_methods = recovery.auth_methods
    if "credential_access" in disputed and not (
        recovery.credential_access.value == CredentialAccess.UNKNOWN
        and first_pass.credential_access.value != CredentialAccess.UNKNOWN
    ):
        merged.credential_access = recovery.credential_access
    if "api_availability" in disputed and not (
        recovery.api_availability.value == ApiAvailability.UNKNOWN
        and first_pass.api_availability.value != ApiAvailability.UNKNOWN
    ):
        merged.api_availability = recovery.api_availability
    if "api_breadth" in disputed and not (
        recovery.api_breadth.value == ApiBreadth.UNKNOWN
        and first_pass.api_breadth.value != ApiBreadth.UNKNOWN
    ):
        merged.api_breadth = recovery.api_breadth
    if "callable_interface" in disputed or "buildability_path" in disputed:
        if recovery.api_styles or not first_pass.api_styles:
            merged.api_styles = recovery.api_styles
        for field in ("webhooks", "official_sdk", "cli"):
            recovered_claim = getattr(recovery, field)
            first_claim = getattr(first_pass, field)
            if recovered_claim.value != Ternary.UNKNOWN or first_claim.value == Ternary.UNKNOWN:
                setattr(merged, field, recovered_claim)
        if (
            recovery.api_surface_summary.value is not None
            or first_pass.api_surface_summary.value is None
        ):
            merged.api_surface_summary = recovery.api_surface_summary
    merged.unresolved_questions = list(
        dict.fromkeys([*first_pass.unresolved_questions, *recovery.unresolved_questions])
    )
    return AppResearchDraft.model_validate(merged.model_dump())
