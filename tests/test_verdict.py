from integration_research.models import (
    ApiAvailability,
    ApiBreadth,
    Claim,
    CommercialRequirement,
    McpStatus,
    ProductionGate,
    Ternary,
)
from integration_research.verdict import compute_buildability, derive_integration_paths
from tests.helpers import API_QUOTE, evidence, make_valid_draft


def test_broad_self_serve_api_is_buildable() -> None:
    draft = make_valid_draft()
    assert compute_buildability(draft).value == "yes"
    assert derive_integration_paths(draft) == ["cli", "graphql", "official_mcp", "rest"]


def test_paid_or_approval_gates_are_conditional() -> None:
    draft = make_valid_draft()
    draft.production_gate = Claim[ProductionGate](
        value=ProductionGate.APP_REVIEW,
        evidence=evidence("source_3", API_QUOTE),
    )
    assert compute_buildability(draft).value == "conditional"

    draft = make_valid_draft()
    draft.commercial_requirement = Claim[CommercialRequirement](
        value=CommercialRequirement.PAID_PLAN,
        evidence=evidence("source_3", API_QUOTE),
    )
    assert compute_buildability(draft).value == "conditional"


def test_narrow_or_read_only_api_is_conditional() -> None:
    draft = make_valid_draft()
    draft.api_breadth.value = ApiBreadth.NARROW
    assert compute_buildability(draft).value == "conditional"
    draft.api_breadth.value = ApiBreadth.BROAD
    draft.api_capabilities.write.value = Ternary.NO
    assert compute_buildability(draft).value == "conditional"


def test_webhooks_and_sdk_alone_do_not_establish_buildability() -> None:
    draft = make_valid_draft()
    draft.api_availability.value = ApiAvailability.UNKNOWN
    draft.api_styles = []
    draft.cli.value = Ternary.NO
    draft.mcp_status.value = McpStatus.UNKNOWN
    draft.webhooks.value = Ternary.YES
    draft.official_sdk.value = Ternary.YES
    assert compute_buildability(draft).value == "unknown"
    assert derive_integration_paths(draft) == []


def test_unknown_material_gating_makes_verdict_unknown() -> None:
    draft = make_valid_draft()
    draft.commercial_requirement.value = CommercialRequirement.UNKNOWN
    assert compute_buildability(draft).value == "unknown"
