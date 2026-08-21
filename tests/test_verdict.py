from integration_research.models import (
    ApiAvailability,
    ApiBreadth,
    Claim,
    DeveloperAccess,
    ProductionGate,
    Ternary,
)
from integration_research.verdict import compute_buildability, derive_integration_paths
from tests.helpers import API_QUOTE, evidence, make_valid_draft


def test_broad_self_serve_api_is_buildable() -> None:
    draft = make_valid_draft()
    assert compute_buildability(draft).value == "yes"
    assert derive_integration_paths(draft) == ["graphql", "rest"]


def test_paid_or_approval_gates_are_conditional() -> None:
    draft = make_valid_draft()
    draft.production_gates = [
        Claim[ProductionGate](
            value=ProductionGate.APP_REVIEW,
            evidence=evidence("source_3", API_QUOTE),
        )
    ]
    assert compute_buildability(draft).value == "conditional"


def test_narrow_or_read_only_api_is_conditional() -> None:
    draft = make_valid_draft()
    draft.api_breadth.value = ApiBreadth.NARROW
    assert compute_buildability(draft).value == "conditional"
    draft.api_breadth.value = ApiBreadth.BROAD
    draft.api_capabilities.write.value = Ternary.NO
    assert compute_buildability(draft).value == "conditional"


def test_explicit_absence_is_no_and_missing_surface_is_unknown() -> None:
    draft = make_valid_draft()
    draft.api_availability.value = ApiAvailability.NO
    draft.api_protocols = []
    assert compute_buildability(draft).value == "no"

    draft.api_availability.value = ApiAvailability.UNKNOWN
    draft.developer_access.value = DeveloperAccess.UNKNOWN
    assert compute_buildability(draft).value == "unknown"
