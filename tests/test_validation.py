from integration_research.models import (
    ApiAvailability,
    ApiBreadth,
    Claim,
    CommercialRequirement,
    EvidenceRef,
    ProductionGate,
    Ternary,
)
from integration_research.validation import quote_exists, validate_draft
from tests.helpers import evidence, make_app_input, make_snippets, make_sources, make_valid_draft


def test_quote_validation_normalizes_unicode_and_whitespace() -> None:
    assert quote_exists("OAuth\u00a0token", "Use an OAuth   token for requests.")
    assert quote_exists(
        "Use a [personal access token] for requests.",
        "Use a [personal access token](https://example.test/token) for requests.",
    )
    assert quote_exists("Click Generate token.", "Click **Generate token**.")
    assert not quote_exists("invented evidence", "Use an OAuth token for requests.")


def test_validation_rejects_unknown_snippet() -> None:
    draft = make_valid_draft()
    draft.description.evidence = [
        EvidenceRef(source_id="source_5", snippet_id="source_5_snippet_999")
    ]
    report = validate_draft(
        draft,
        app_input=make_app_input(),
        sources=make_sources(),
        snippets=make_snippets(),
    )
    assert not report.valid
    assert {issue.code for issue in report.errors} == {"unknown_snippet"}


def test_production_none_and_free_access_require_literal_evidence() -> None:
    draft = make_valid_draft()
    draft.production_gate = Claim[ProductionGate](value=ProductionGate.NONE, evidence=[])
    draft.commercial_requirement = Claim[CommercialRequirement](
        value=CommercialRequirement.FREE_AVAILABLE, evidence=[]
    )
    report = validate_draft(
        draft,
        app_input=make_app_input(),
        sources=make_sources(),
        snippets=make_snippets(),
    )
    assert not report.valid
    missing_fields = {issue.field for issue in report.errors if issue.code == "missing_evidence"}
    assert missing_fields == {"commercial_requirement", "production_gate"}


def test_structural_validation_rejects_api_contradictions() -> None:
    draft = make_valid_draft()
    draft.api_availability = Claim[ApiAvailability](
        value=ApiAvailability.NO,
        evidence=evidence("source_3", "ignored"),
    )
    sources = make_sources()
    draft.api_breadth = Claim[ApiBreadth](value=ApiBreadth.BROAD, evidence=[])
    draft.api_capabilities.read = Claim[Ternary](value=Ternary.YES, evidence=[])
    report = validate_draft(
        draft,
        app_input=make_app_input(),
        sources=sources,
        snippets=make_snippets(),
    )
    assert not report.valid
    assert "api_contradiction" in {issue.code for issue in report.errors}


def test_explicit_unknowns_are_valid_with_questions() -> None:
    draft = make_valid_draft()
    draft.commercial_requirement = Claim[CommercialRequirement](
        value=CommercialRequirement.UNKNOWN, evidence=[]
    )
    draft.production_gate = Claim[ProductionGate](value=ProductionGate.UNKNOWN, evidence=[])
    draft.unresolved_questions.extend(
        [
            "What commercial plan is required for GitHub API access?",
            "Does GitHub require production approval or review?",
        ]
    )
    report = validate_draft(
        draft,
        app_input=make_app_input(),
        sources=make_sources(),
        snippets=make_snippets(),
    )
    assert report.valid
    assert set(report.unknown_fields) == {"commercial_requirement", "production_gate"}
