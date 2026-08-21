import pytest
from pydantic import ValidationError

from integration_research.models import AppResearchDraft, AuthMethod, AuthMethodDraft, EvidenceRef
from tests.helpers import make_valid_draft


def test_schema_accepts_multiple_confirmed_auth_methods_with_details() -> None:
    draft = make_valid_draft()
    draft.auth_methods.append(
        AuthMethodDraft(
            method=AuthMethod.BASIC,
            details="Basic authentication for selected app endpoints",
            evidence=[EvidenceRef(source_id="source_1", snippet_id="source_1_snippet_001")],
        )
    )
    validated = AppResearchDraft.model_validate(draft.model_dump())
    assert len(validated.auth_methods) == 2


def test_schema_rejects_unknown_with_confirmed_auth() -> None:
    payload = make_valid_draft().model_dump()
    payload["auth_methods"].append({"method": "unknown", "details": None, "evidence": []})
    with pytest.raises(ValidationError, match="unknown authentication"):
        AppResearchDraft.model_validate(payload)


def test_schema_rejects_removed_auth_and_api_style_categories() -> None:
    payload = make_valid_draft().model_dump()
    payload["auth_methods"][0]["method"] = "bearer_token"
    with pytest.raises(ValidationError, match=r"auth_methods\.0\.method"):
        AppResearchDraft.model_validate(payload)

    payload = make_valid_draft().model_dump()
    payload["api_styles"][0]["value"] = "webhook"
    with pytest.raises(ValidationError, match=r"api_styles\.0\.value"):
        AppResearchDraft.model_validate(payload)

    payload["api_styles"][0]["value"] = "cli"
    with pytest.raises(ValidationError, match=r"api_styles\.0\.value"):
        AppResearchDraft.model_validate(payload)

    payload["api_styles"][0]["value"] = "sdk_only"
    with pytest.raises(ValidationError, match=r"api_styles\.0\.value"):
        AppResearchDraft.model_validate(payload)


def test_schema_rejects_extra_fields_and_invalid_snippet_ids() -> None:
    payload = make_valid_draft().model_dump()
    payload["model_verdict"] = "yes"
    with pytest.raises(ValidationError, match="Extra inputs"):
        AppResearchDraft.model_validate(payload)
    with pytest.raises(ValidationError, match="snippet_id"):
        EvidenceRef(source_id="source_1", snippet_id="invented")
