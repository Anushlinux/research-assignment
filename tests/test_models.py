import pytest
from pydantic import ValidationError

from integration_research.models import AppResearchDraft, AuthMethod, Claim, EvidenceRef
from tests.helpers import AUTH_QUOTE, make_valid_draft


def test_schema_accepts_multiple_confirmed_auth_methods() -> None:
    draft = make_valid_draft()
    draft.auth_methods.append(
        Claim[AuthMethod](
            value=AuthMethod.BEARER_TOKEN,
            evidence=[EvidenceRef(source_id="source_1", quote=AUTH_QUOTE)],
        )
    )
    validated = AppResearchDraft.model_validate(draft.model_dump())
    assert len(validated.auth_methods) == 2


def test_schema_rejects_unknown_with_confirmed_auth() -> None:
    payload = make_valid_draft().model_dump()
    payload["auth_methods"].append({"value": "unknown", "evidence": []})
    with pytest.raises(ValidationError, match="unknown authentication"):
        AppResearchDraft.model_validate(payload)


def test_schema_rejects_extra_fields_and_long_quotes() -> None:
    payload = make_valid_draft().model_dump()
    payload["model_verdict"] = "yes"
    with pytest.raises(ValidationError, match="Extra inputs"):
        AppResearchDraft.model_validate(payload)
    with pytest.raises(ValidationError, match="at most 500"):
        EvidenceRef(source_id="source_1", quote="x" * 501)
