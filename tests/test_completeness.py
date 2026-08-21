from integration_research.completeness import (
    assess_completeness,
    assess_source_quality,
    auth_taxonomy_warnings,
    merge_disputed_fields,
)
from integration_research.models import (
    ApiAvailability,
    AuthMethod,
    AuthMethodDraft,
    CredentialAccess,
    SourceRole,
    Ternary,
)
from tests.helpers import evidence, make_sources, make_valid_draft


def test_podio_marketing_homepage_is_not_adequate_api_evidence() -> None:
    quality = assess_source_quality(
        role=SourceRole.API_SURFACE,
        url="https://podio.com/",
        text="Podio helps teams work together with flexible workflows and robust APIs.",
    )

    assert not quality.sufficient
    assert quality.generic_homepage
    assert "Generic homepage" in quality.reason


def test_attio_oauth_evidence_routes_wrong_other_enum_to_verification() -> None:
    draft = make_valid_draft()
    draft.auth_methods = [
        AuthMethodDraft(
            method=AuthMethod.OTHER,
            details="Public app authentication",
            evidence=evidence("source_1", "unused"),
        )
    ]
    sources = make_sources()
    sources["source_1"].url = "https://docs.attio.com/rest-api/guides/oauth"
    sources["source_1"].text = (
        "Use the OAuth authorization code flow with a client ID and client secret. "
        "Exchange the code for a bearer access token."
    )

    warnings = auth_taxonomy_warnings(draft, sources)
    report = assess_completeness(draft, sources, taxonomy_warnings=warnings)

    assert warnings
    assert "auth_methods" in report.critical_unknown_fields
    assert report.requires_verification


def test_role_quality_requires_developer_content_not_only_a_good_url() -> None:
    weak = assess_source_quality(
        role=SourceRole.API_SURFACE,
        url="https://docs.example.test/api",
        text="Welcome to our developer platform.",
    )
    strong = assess_source_quality(
        role=SourceRole.API_SURFACE,
        url="https://docs.example.test/api/reference",
        text="API reference endpoint. Send a GET request and inspect the response.",
    )

    assert not weak.sufficient
    assert strong.sufficient


def test_recovery_unknown_cannot_erase_known_first_pass_values() -> None:
    first = make_valid_draft()
    recovery = make_valid_draft()
    recovery.auth_methods = [AuthMethodDraft(method=AuthMethod.UNKNOWN, details=None, evidence=[])]
    recovery.credential_access = recovery.credential_access.model_copy(
        update={"value": CredentialAccess.UNKNOWN, "evidence": []}
    )
    recovery.api_availability = recovery.api_availability.model_copy(
        update={"value": ApiAvailability.UNKNOWN, "evidence": []}
    )

    merged = merge_disputed_fields(
        first,
        recovery,
        ["auth_methods", "credential_access", "api_availability"],
    )

    assert [item.method for item in merged.auth_methods] == [AuthMethod.TOKEN]
    assert merged.credential_access.value == CredentialAccess.SELF_SERVE
    assert merged.api_availability.value == ApiAvailability.YES


def test_documented_local_cli_does_not_require_remote_auth_role_signals() -> None:
    draft = make_valid_draft()
    draft.auth_methods = [AuthMethodDraft(method=AuthMethod.NONE, details="Local CLI", evidence=[])]
    draft.credential_access = draft.credential_access.model_copy(
        update={"value": CredentialAccess.NOT_REQUIRED, "evidence": []}
    )
    draft.cli = draft.cli.model_copy(update={"value": Ternary.YES})

    report = assess_completeness(draft, make_sources())

    assert SourceRole.AUTHENTICATION.value not in report.weak_source_roles
    assert SourceRole.CREDENTIAL_ACCESS.value not in report.weak_source_roles
