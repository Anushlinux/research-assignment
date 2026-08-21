"""Independent, tool-free claim-to-evidence auditing and deterministic admission."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from openai import OpenAI

from integration_research.models import (
    AdmissionChange,
    AdmissionReport,
    ApiAvailability,
    ApiBreadth,
    AppResearchDraft,
    AuditClaimInput,
    AuditDecision,
    AuditEvidenceContext,
    AuthMethod,
    AuthMethodDraft,
    ClaimAuditResult,
    CommercialRequirement,
    CredentialAccess,
    EvidenceSnippet,
    FetchedSource,
    McpStatus,
    ProductionGate,
    SemanticAuditInput,
    SemanticAuditResponse,
    Ternary,
)
from integration_research.settings import Settings
from integration_research.validation import (
    is_unknown,
    iter_material_claims,
    normalize_evidence_text,
)

AUDIT_PROMPT_VERSION = "catalog-evidence-audit-v3"
AUDIT_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "audit.md"

FIELD_DEFINITIONS: dict[str, str] = {
    "description": "A one-line factual description of the named product.",
    "auth_methods": (
        "High-level authentication method. OAuth2 requires explicit OAuth 2.0 evidence or "
        "dedicated OAuth application documentation. Transport wording is not a second method. "
        "A documented fully local command over local files can support none for that path."
    ),
    "credential_access": (
        "How credentials can be obtained, separate from price and production. A documented fully "
        "local install-and-run path can support not_required for that path."
    ),
    "commercial_requirement": "The account, trial, paid-plan, or enterprise requirement.",
    "production_gate": (
        "Approval required for production use. None is a positive claim requiring direct evidence."
    ),
    "api_availability": "Whether a documented callable developer API is available.",
    "api_styles": "Callable API style: REST, GraphQL, RPC, or another callable public API.",
    "webhooks": "Whether the product documents webhooks or an event-delivery interface.",
    "official_sdk": "Whether the vendor documents an official software development kit.",
    "cli": "Whether a documented usable command-line interface exposes meaningful operations.",
    "api_breadth": "How broadly the callable API covers meaningful product resources.",
    "api_capabilities": (
        "Whether the callable API directly supports the stated read or write action."
    ),
    "api_surface_summary": "A concise summary of operations directly established by the evidence.",
    "mcp_status": "Official, community, bounded not-found, or unknown MCP status.",
    "blocker": "A documented fact that materially blocks an agent-callable integration.",
}

UNRESOLVED_QUESTIONS: dict[str, str] = {
    "description": "What concise description of {app_name} is directly supported by the sources?",
    "auth_methods": "Which high-level {app_name} authentication methods are documented?",
    "credential_access": "Can a developer obtain {app_name} credentials without external approval?",
    "commercial_requirement": "What commercial plan is required for {app_name} interface access?",
    "production_gate": "Does {app_name} require review or approval for production use?",
    "api_availability": "Does {app_name} expose a supported callable developer API?",
    "api_styles": "Which callable API styles does {app_name} document?",
    "webhooks": "Does {app_name} document webhook or event delivery support?",
    "official_sdk": "Does {app_name} document an official SDK for this interface?",
    "cli": "Does {app_name} document a usable CLI with meaningful callable operations?",
    "api_breadth": "How broad is the documented {app_name} callable API surface?",
    "api_capabilities": "Which read and write capabilities does the {app_name} API support?",
    "api_surface_summary": "Which {app_name} interface operations are supported by evidence?",
    "mcp_status": "Was an official or community MCP server found for {app_name}?",
    "blocker": "Is there a documented blocker to building a {app_name} integration?",
}


@dataclass(frozen=True)
class AuditExecution:
    response: SemanticAuditResponse
    response_id: str
    input_tokens: int
    output_tokens: int


class AuditClient(Protocol):
    model: str

    def audit(self, *, instructions: str, audit_input: SemanticAuditInput) -> AuditExecution: ...


class OpenAIAuditClient:
    """One structured-output call with no tools and no browsing."""

    def __init__(self, settings: Settings) -> None:
        if settings.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is required")
        self.model = settings.openai_model_verify
        self._client = OpenAI(api_key=settings.openai_api_key.get_secret_value(), max_retries=0)

    def audit(self, *, instructions: str, audit_input: SemanticAuditInput) -> AuditExecution:
        response = self._client.responses.parse(
            model=self.model,
            instructions=instructions,
            input=audit_input.model_dump_json(indent=2),
            reasoning={"effort": "low"},
            text_format=SemanticAuditResponse,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("OpenAI returned no parsed SemanticAuditResponse")
        usage = response.usage
        return AuditExecution(
            response=parsed,
            response_id=response.id,
            input_tokens=usage.input_tokens if usage is not None else 0,
            output_tokens=usage.output_tokens if usage is not None else 0,
        )


def load_audit_prompt() -> str:
    return AUDIT_PROMPT_PATH.read_text(encoding="utf-8")


def _root(field: str) -> str:
    return field.split("[", 1)[0].split(".", 1)[0]


def _field_definition(field: str) -> str:
    return FIELD_DEFINITIONS[_root(field)]


def _normalized_claim(draft: AppResearchDraft, field: str, value: object) -> str:
    if field.startswith("auth_methods["):
        index = int(field.removeprefix("auth_methods[").removesuffix("]"))
        item = draft.auth_methods[index]
        return f"Authentication supports {item.method.value}: {item.details}"
    if field.startswith("api_styles["):
        return f"The callable API style is {value}."
    return f"{field} = {value}"


def _context_for(quote: str, source_text: str, *, radius: int = 350) -> str:
    text = normalize_evidence_text(source_text)
    needle = normalize_evidence_text(quote)
    index = text.find(needle)
    if index < 0:
        raise ValueError("quotation disappeared while constructing semantic audit context")
    start = max(0, index - radius)
    end = min(len(text), index + len(needle) + radius)
    return text[start:end]


def build_audit_input(
    draft: AppResearchDraft,
    sources: dict[str, FetchedSource],
    snippets: dict[str, EvidenceSnippet],
) -> SemanticAuditInput:
    claims: list[AuditClaimInput] = []
    for material in iter_material_claims(draft):
        if is_unknown(material.value):
            continue
        contexts = []
        for reference in material.evidence:
            source = sources[reference.source_id]
            snippet = snippets[reference.snippet_id]
            contexts.append(
                AuditEvidenceContext(
                    source_id=source.source_id,
                    source_title=source.title,
                    source_roles=source.source_roles or [source.source_role],
                    quote=snippet.text,
                    context=_context_for(snippet.text, source.text),
                )
            )
        claims.append(
            AuditClaimInput(
                claim_id=f"claim_{len(claims) + 1:03d}",
                field=material.field,
                field_definition=_field_definition(material.field),
                normalized_claim=_normalized_claim(draft, material.field, material.value),
                evidence=contexts,
            )
        )
    return SemanticAuditInput(app_id=draft.app_id, app_name=draft.app_name, claims=claims)


def validate_audit_response(
    audit_input: SemanticAuditInput, response: SemanticAuditResponse
) -> None:
    expected = {claim.claim_id for claim in audit_input.claims}
    returned = [result.claim_id for result in response.results]
    if len(returned) != len(set(returned)):
        raise ValueError("semantic audit contains duplicate claim IDs")
    missing = expected - set(returned)
    unexpected = set(returned) - expected
    if missing or unexpected:
        raise ValueError(
            "semantic audit is incomplete or contradictory: "
            f"missing={sorted(missing)}, unexpected={sorted(unexpected)}"
        )


def _oauth_token_can_narrow(claim: AuditClaimInput) -> bool:
    combined = " ".join(item.quote for item in claim.evidence).lower()
    explicitly_oauth2 = bool(re.search(r"oauth\s*2(?:\.0)?", combined))
    return "oauth token" in combined and not explicitly_oauth2


def _add_question(draft: AppResearchDraft, field: str) -> None:
    question = UNRESOLVED_QUESTIONS[_root(field)].format(app_name=draft.app_name)
    if question not in draft.unresolved_questions:
        draft.unresolved_questions.append(question)


def _unknown_scalar(draft: AppResearchDraft, field: str) -> object:
    if field == "description":
        draft.description = draft.description.model_copy(update={"value": None, "evidence": []})
        return None
    if field == "credential_access":
        draft.credential_access = draft.credential_access.model_copy(
            update={"value": CredentialAccess.UNKNOWN, "evidence": []}
        )
        return CredentialAccess.UNKNOWN
    if field == "commercial_requirement":
        draft.commercial_requirement = draft.commercial_requirement.model_copy(
            update={"value": CommercialRequirement.UNKNOWN, "evidence": []}
        )
        return CommercialRequirement.UNKNOWN
    if field == "production_gate":
        draft.production_gate = draft.production_gate.model_copy(
            update={"value": ProductionGate.UNKNOWN, "evidence": []}
        )
        return ProductionGate.UNKNOWN
    if field == "api_availability":
        draft.api_availability = draft.api_availability.model_copy(
            update={"value": ApiAvailability.UNKNOWN, "evidence": []}
        )
        return ApiAvailability.UNKNOWN
    if field in {"webhooks", "official_sdk", "cli"}:
        claim = getattr(draft, field)
        setattr(draft, field, claim.model_copy(update={"value": Ternary.UNKNOWN, "evidence": []}))
        return Ternary.UNKNOWN
    if field == "api_breadth":
        draft.api_breadth = draft.api_breadth.model_copy(
            update={"value": ApiBreadth.UNKNOWN, "evidence": []}
        )
        return ApiBreadth.UNKNOWN
    if field == "api_capabilities.read":
        draft.api_capabilities.read = draft.api_capabilities.read.model_copy(
            update={"value": Ternary.UNKNOWN, "evidence": []}
        )
        return Ternary.UNKNOWN
    if field == "api_capabilities.write":
        draft.api_capabilities.write = draft.api_capabilities.write.model_copy(
            update={"value": Ternary.UNKNOWN, "evidence": []}
        )
        return Ternary.UNKNOWN
    if field == "api_surface_summary":
        draft.api_surface_summary = draft.api_surface_summary.model_copy(
            update={"value": None, "evidence": []}
        )
        return None
    if field == "mcp_status":
        draft.mcp_status = draft.mcp_status.model_copy(
            update={"value": McpStatus.UNKNOWN, "evidence": []}
        )
        return McpStatus.UNKNOWN
    if field == "blocker":
        draft.blocker = None
        return None
    raise ValueError(f"no deterministic unknown mapping for {field}")


def apply_semantic_audit(
    draft: AppResearchDraft,
    audit_input: SemanticAuditInput,
    response: SemanticAuditResponse,
) -> tuple[AppResearchDraft, AdmissionReport]:
    """Admit only direct support plus the single explicit OAuth-token narrowing."""

    validate_audit_response(audit_input, response)
    admitted = draft.model_copy(deep=True)
    input_by_id = {claim.claim_id: claim for claim in audit_input.claims}
    result_by_id = {result.claim_id: result for result in response.results}
    auth_removals: list[int] = []
    style_removals: list[int] = []
    changes: list[AdmissionChange] = []

    for claim_id, audit_claim in input_by_id.items():
        result: ClaimAuditResult = result_by_id[claim_id]
        if result.decision == AuditDecision.DIRECT_SUPPORT:
            continue
        field = audit_claim.field
        if field.startswith("auth_methods["):
            index = int(field.removeprefix("auth_methods[").removesuffix("]"))
            item = admitted.auth_methods[index]
            old = item.method
            if (
                result.decision == AuditDecision.PARTIAL_SUPPORT
                and item.method == AuthMethod.OAUTH2
                and _oauth_token_can_narrow(audit_claim)
            ):
                item.method = AuthMethod.TOKEN
                item.details = "OAuth token"
                new: object = AuthMethod.TOKEN
            else:
                auth_removals.append(index)
                new = AuthMethod.UNKNOWN
                _add_question(admitted, field)
            changes.append(
                AdmissionChange(
                    field=field,
                    old_value=old,
                    new_value=new,
                    decision=result.decision,
                    reason=result.reason,
                )
            )
            continue
        if field.startswith("api_styles["):
            index = int(field.removeprefix("api_styles[").removesuffix("]"))
            old_style = admitted.api_styles[index].value
            style_removals.append(index)
            _add_question(admitted, field)
            changes.append(
                AdmissionChange(
                    field=field,
                    old_value=old_style,
                    new_value=None,
                    decision=result.decision,
                    reason=result.reason,
                )
            )
            continue

        old_material = next(item for item in iter_material_claims(admitted) if item.field == field)
        new_value = _unknown_scalar(admitted, field)
        _add_question(admitted, field)
        changes.append(
            AdmissionChange(
                field=field,
                old_value=old_material.value,
                new_value=new_value,
                decision=result.decision,
                reason=result.reason,
            )
        )

    for index in sorted(set(auth_removals), reverse=True):
        admitted.auth_methods.pop(index)
    for index in sorted(set(style_removals), reverse=True):
        admitted.api_styles.pop(index)

    deduplicated: list[AuthMethodDraft] = []
    seen_methods: set[AuthMethod] = set()
    for item in admitted.auth_methods:
        if item.method in seen_methods:
            continue
        deduplicated.append(item)
        seen_methods.add(item.method)
    admitted.auth_methods = deduplicated
    if not admitted.auth_methods:
        admitted.auth_methods = [
            AuthMethodDraft(method=AuthMethod.UNKNOWN, details=None, evidence=[])
        ]
    return AppResearchDraft.model_validate(admitted.model_dump()), AdmissionReport(changes=changes)
