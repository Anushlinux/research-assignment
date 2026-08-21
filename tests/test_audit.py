import pytest

from integration_research.audit import (
    apply_semantic_audit,
    build_audit_input,
    validate_audit_response,
)
from integration_research.models import (
    AuditDecision,
    AuthMethod,
    ClaimAuditResult,
    CommercialRequirement,
    EvidenceRef,
    SemanticAuditResponse,
)
from tests.helpers import make_snippets, make_sources, make_valid_draft


def direct_response(claim_ids: list[str]) -> SemanticAuditResponse:
    return SemanticAuditResponse(
        results=[
            ClaimAuditResult(
                claim_id=claim_id,
                decision=AuditDecision.DIRECT_SUPPORT,
                reason="The quotation directly establishes the normalized claim.",
            )
            for claim_id in claim_ids
        ]
    )


def test_oauth_token_partially_supported_claim_narrows_to_token() -> None:
    draft = make_valid_draft()
    quote = "You can also create an OAuth token with an OAuth app."
    sources = make_sources()
    snippets = make_snippets()
    sources["source_1"].text += f" {quote}"
    snippets["source_1_snippet_001"].text = quote
    draft.auth_methods[0].method = AuthMethod.OAUTH2
    draft.auth_methods[0].details = "OAuth app token"
    draft.auth_methods[0].evidence = [
        EvidenceRef(source_id="source_1", snippet_id="source_1_snippet_001")
    ]
    audit_input = build_audit_input(draft, sources, snippets)
    response = direct_response([claim.claim_id for claim in audit_input.claims])
    auth_claim = next(claim for claim in audit_input.claims if claim.field == "auth_methods[0]")
    result = next(item for item in response.results if item.claim_id == auth_claim.claim_id)
    result.decision = AuditDecision.PARTIAL_SUPPORT
    result.reason = "The source says OAuth token but does not establish OAuth 2.0."

    admitted, report = apply_semantic_audit(draft, audit_input, response)
    assert admitted.auth_methods[0].method == AuthMethod.TOKEN
    assert report.changes[0].new_value == AuthMethod.TOKEN


def test_unsupported_commercial_claim_becomes_unknown_not_failure() -> None:
    draft = make_valid_draft()
    draft.app_name = "Example Product"
    audit_input = build_audit_input(draft, make_sources(), make_snippets())
    response = direct_response([claim.claim_id for claim in audit_input.claims])
    commercial = next(
        claim for claim in audit_input.claims if claim.field == "commercial_requirement"
    )
    result = next(item for item in response.results if item.claim_id == commercial.claim_id)
    result.decision = AuditDecision.UNSUPPORTED
    result.reason = "Credential creation does not establish that a free account is sufficient."

    admitted, report = apply_semantic_audit(draft, audit_input, response)
    assert admitted.commercial_requirement.value == CommercialRequirement.UNKNOWN
    assert admitted.commercial_requirement.evidence == []
    assert any("commercial" in question.lower() for question in admitted.unresolved_questions)
    assert any("Example Product" in question for question in admitted.unresolved_questions)
    assert report.changes[0].field == "commercial_requirement"


def test_incomplete_semantic_audit_is_fatal() -> None:
    draft = make_valid_draft()
    audit_input = build_audit_input(draft, make_sources(), make_snippets())
    response = direct_response([audit_input.claims[0].claim_id])
    with pytest.raises(ValueError, match="incomplete or contradictory"):
        validate_audit_response(audit_input, response)
