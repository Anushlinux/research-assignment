from integration_research.models import (
    ApiAvailability,
    ApiBreadth,
    ApiCapabilitiesDraft,
    Claim,
    DeveloperAccess,
    EvidenceRef,
    McpStatus,
    Ternary,
)
from integration_research.validation import (
    normalize_unsupported_negatives,
    quote_exists,
    validate_draft,
)
from tests.helpers import make_app_input, make_sources, make_valid_draft


def test_quote_validation_normalizes_unicode_and_whitespace() -> None:
    assert quote_exists("OAuth\u00a0token", "Use an OAuth   token for requests.")
    assert not quote_exists("invented evidence", "Use an OAuth token for requests.")


def test_validation_rejects_unknown_source_and_fabricated_quote() -> None:
    draft = make_valid_draft()
    draft.description.evidence = [
        EvidenceRef(source_id="source_4", quote="This quotation was invented.")
    ]
    report = validate_draft(draft, app_input=make_app_input(), sources=make_sources())
    assert not report.valid
    assert {issue.code for issue in report.errors} == {"quote_not_found"}


def test_unproven_negative_claims_become_unknown() -> None:
    draft = make_valid_draft()
    draft.api_availability = Claim[ApiAvailability](
        value=ApiAvailability.NO,
        evidence=[EvidenceRef(source_id="source_3", quote="repository read and write operations")],
    )
    draft.developer_access = Claim[DeveloperAccess](
        value=DeveloperAccess.NOT_AVAILABLE,
        evidence=[EvidenceRef(source_id="source_2", quote="create credentials")],
    )
    draft.mcp_status = Claim[McpStatus](value=McpStatus.NOT_FOUND, evidence=[])
    normalized, changes = normalize_unsupported_negatives(draft, make_sources())
    assert normalized.api_availability.value == ApiAvailability.UNKNOWN
    assert normalized.developer_access.value == DeveloperAccess.UNKNOWN
    assert normalized.mcp_status.value == McpStatus.UNKNOWN
    assert {change.code for change in changes} == {
        "negative_api_normalized",
        "negative_access_normalized",
        "negative_mcp_normalized",
    }


def test_semantic_validation_rejects_api_contradictions() -> None:
    draft = make_valid_draft()
    draft.api_availability = Claim[ApiAvailability](
        value=ApiAvailability.NO,
        evidence=[
            EvidenceRef(
                source_id="source_3",
                quote="does not support a public API",
            )
        ],
    )
    sources = make_sources()
    sources["source_3"].text += " GitHub does not support a public API."
    draft.api_breadth = Claim[ApiBreadth](value=ApiBreadth.BROAD, evidence=[])
    draft.api_capabilities = ApiCapabilitiesDraft(
        read=Claim[Ternary](value=Ternary.YES, evidence=[]),
        write=Claim[Ternary](value=Ternary.YES, evidence=[]),
        webhooks_or_events=Claim[Ternary](value=Ternary.YES, evidence=[]),
    )
    normalized, changes = normalize_unsupported_negatives(draft, sources)
    report = validate_draft(
        normalized,
        app_input=make_app_input(),
        sources=sources,
        normalizations=changes,
    )
    assert not report.valid
    assert "api_contradiction" in {issue.code for issue in report.errors}
