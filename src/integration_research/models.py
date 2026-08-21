"""Strict data contracts for the catalog-driven research path."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base model that refuses fields outside the documented contract."""

    model_config = ConfigDict(extra="forbid")


class AuthMethod(StrEnum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BASIC = "basic"
    TOKEN = "token"
    OTHER = "other"
    NONE = "none"
    UNKNOWN = "unknown"


class CredentialAccess(StrEnum):
    SELF_SERVE = "self_serve"
    ADMIN_REQUIRED = "admin_required"
    VENDOR_APPROVAL = "vendor_approval"
    PARTNER_ONLY = "partner_only"
    CONTACT_SALES = "contact_sales"
    NOT_AVAILABLE = "not_available"
    NOT_REQUIRED = "not_required"
    UNKNOWN = "unknown"


class CommercialRequirement(StrEnum):
    FREE_AVAILABLE = "free_available"
    TRIAL_AVAILABLE = "trial_available"
    PAID_PLAN = "paid_plan"
    ENTERPRISE_ONLY = "enterprise_only"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class ProductionGate(StrEnum):
    NONE = "none"
    APP_REVIEW = "app_review"
    ADMIN_APPROVAL = "admin_approval"
    VENDOR_APPROVAL = "vendor_approval"
    PARTNER_APPROVAL = "partner_approval"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class ApiAvailability(StrEnum):
    YES = "yes"
    LIMITED = "limited"
    NO = "no"
    UNKNOWN = "unknown"


class ApiStyle(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"
    RPC = "rpc"
    OTHER = "other"


class ApiBreadth(StrEnum):
    BROAD = "broad"
    MODERATE = "moderate"
    NARROW = "narrow"
    NONE = "none"
    UNKNOWN = "unknown"


class Ternary(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class McpStatus(StrEnum):
    OFFICIAL = "official"
    COMMUNITY = "community"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


class Buildability(StrEnum):
    YES = "yes"
    CONDITIONAL = "conditional"
    NO = "no"
    UNKNOWN = "unknown"


class RecordStatus(StrEnum):
    FIRST_PASS_STRUCTURALLY_VALID = "first_pass_structurally_valid"
    NEEDS_VERIFICATION = "needs_verification"
    VERIFIED = "verified"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    FAILED = "failed"


class SourceTier(StrEnum):
    OFFICIAL_DEVELOPER_DOCS = "official_developer_docs"
    OFFICIAL_REPOSITORY = "official_repository"
    OFFICIAL_HELP = "official_help"
    OFFICIAL_PRICING = "official_pricing"
    OFFICIAL_BLOG = "official_blog"
    OFFICIAL_WEBSITE = "official_website"


class SourceRole(StrEnum):
    AUTHENTICATION = "authentication"
    CREDENTIAL_ACCESS = "credential_access"
    API_SURFACE = "api_surface"
    COMMERCIAL_OR_PRODUCTION_GATE = "commercial_or_production_gate"
    MCP = "mcp"


class AuditDecision(StrEnum):
    DIRECT_SUPPORT = "direct_support"
    PARTIAL_SUPPORT = "partial_support"
    UNSUPPORTED = "unsupported"


class EvidenceRef(StrictModel):
    source_id: str = Field(pattern=r"^source_[1-9][0-9]*$")
    snippet_id: str = Field(pattern=r"^source_[1-9][0-9]*_snippet_[0-9]{3}$")


class Claim[ValueT](StrictModel):
    value: ValueT
    evidence: list[EvidenceRef]


class AuthMethodDraft(StrictModel):
    method: AuthMethod
    details: str | None
    evidence: list[EvidenceRef]

    @model_validator(mode="after")
    def validate_details(self) -> AuthMethodDraft:
        if self.method == AuthMethod.UNKNOWN:
            # Conditional evidence constraints are not represented in the JSON schema sent to the
            # model. Normalize an otherwise useful structured response instead of failing the whole
            # bounded recovery pass after the model attaches evidence to `unknown`.
            self.details = None
            self.evidence = []
            return self
        if self.details is None or not self.details.strip():
            raise ValueError("known authentication requires implementation details")
        return self


class ApiCapabilitiesDraft(StrictModel):
    read: Claim[Ternary]
    write: Claim[Ternary]


class AppResearchDraft(StrictModel):
    app_id: int
    app_name: str
    category: str
    description: Claim[str | None]
    auth_methods: list[AuthMethodDraft] = Field(min_length=1)
    credential_access: Claim[CredentialAccess]
    commercial_requirement: Claim[CommercialRequirement]
    production_gate: Claim[ProductionGate]
    api_availability: Claim[ApiAvailability]
    api_styles: list[Claim[ApiStyle]]
    webhooks: Claim[Ternary]
    official_sdk: Claim[Ternary]
    cli: Claim[Ternary]
    api_breadth: Claim[ApiBreadth]
    api_capabilities: ApiCapabilitiesDraft
    api_surface_summary: Claim[str | None]
    mcp_status: Claim[McpStatus]
    blocker: Claim[str] | None
    unresolved_questions: list[str]

    @model_validator(mode="after")
    def validate_enum_collections(self) -> AppResearchDraft:
        merged_auth: dict[AuthMethod, AuthMethodDraft] = {}
        for item in self.auth_methods:
            existing = merged_auth.get(item.method)
            if existing is None:
                merged_auth[item.method] = item
                continue
            details = list(
                dict.fromkeys(
                    detail
                    for detail in (existing.details, item.details)
                    if detail is not None and detail.strip()
                )
            )
            evidence = list(
                {
                    (reference.source_id, reference.snippet_id): reference
                    for reference in [*existing.evidence, *item.evidence]
                }.values()
            )
            existing.details = "; ".join(details) if details else None
            existing.evidence = evidence
        if len(merged_auth) > 1:
            merged_auth.pop(AuthMethod.UNKNOWN, None)
        self.auth_methods = list(merged_auth.values())

        merged_styles: dict[ApiStyle, Claim[ApiStyle]] = {}
        for claim in self.api_styles:
            existing_style = merged_styles.get(claim.value)
            if existing_style is None:
                merged_styles[claim.value] = claim
                continue
            existing_style.evidence = list(
                {
                    (reference.source_id, reference.snippet_id): reference
                    for reference in [*existing_style.evidence, *claim.evidence]
                }.values()
            )
        self.api_styles = list(merged_styles.values())
        return self


class ResolvedEvidence(StrictModel):
    source_id: str
    url: str
    title: str
    source_tier: SourceTier
    source_role: SourceRole
    source_roles: list[SourceRole]
    quote: str
    retrieved_at: datetime
    content_hash: str


class ResolvedClaim[ValueT](StrictModel):
    value: ValueT
    evidence: list[ResolvedEvidence]


class ResolvedAuthMethod(StrictModel):
    method: AuthMethod
    details: str | None
    evidence: list[ResolvedEvidence]


class ApiCapabilitiesFinal(StrictModel):
    read: ResolvedClaim[Ternary]
    write: ResolvedClaim[Ternary]


class CompletenessReport(StrictModel):
    critical_unknown_fields: list[str]
    weak_source_roles: list[str]
    generic_homepage_only_roles: list[str]
    requires_verification: bool
    eligible_for_final_export: bool


class FinalAppResearch(StrictModel):
    app_id: int
    app_name: str
    website_hint: str
    category: str
    official_domains: list[str]
    description: ResolvedClaim[str | None]
    auth_methods: list[ResolvedAuthMethod]
    credential_access: ResolvedClaim[CredentialAccess]
    commercial_requirement: ResolvedClaim[CommercialRequirement]
    production_gate: ResolvedClaim[ProductionGate]
    api_availability: ResolvedClaim[ApiAvailability]
    api_styles: list[ResolvedClaim[ApiStyle]]
    webhooks: ResolvedClaim[Ternary]
    official_sdk: ResolvedClaim[Ternary]
    cli: ResolvedClaim[Ternary]
    api_breadth: ResolvedClaim[ApiBreadth]
    api_capabilities: ApiCapabilitiesFinal
    api_surface_summary: ResolvedClaim[str | None]
    mcp_status: ResolvedClaim[McpStatus]
    blocker: ResolvedClaim[str] | None
    unresolved_questions: list[str]
    buildability: Buildability
    integration_paths: list[str]
    status: RecordStatus
    completeness: CompletenessReport
    generated_at: datetime
    extraction_model: str
    audit_model: str
    pipeline_version: str
    extraction_prompt_version: str
    audit_prompt_version: str


class AppInput(StrictModel):
    app_id: int
    app_name: str
    website_hint: str
    category: str
    notes: str


class FetchedSource(StrictModel):
    source_id: str
    source_role: SourceRole
    source_roles: list[SourceRole] = Field(default_factory=list)
    url: str
    title: str
    source_tier: SourceTier
    text: str
    successful: bool
    retrieved_at: datetime
    content_hash: str
    log_id: str
    raw_response: dict[str, object]
    latency_ms: int


class EvidenceSnippet(StrictModel):
    snippet_id: str = Field(pattern=r"^source_[1-9][0-9]*_snippet_[0-9]{3}$")
    source_id: str = Field(pattern=r"^source_[1-9][0-9]*$")
    text: str = Field(min_length=1, max_length=500)


class ValidationIssue(StrictModel):
    level: str
    code: str
    field: str
    message: str


class ValidationReport(StrictModel):
    valid: bool
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    normalizations: list[ValidationIssue]
    unknown_fields: list[str]


class AuditEvidenceContext(StrictModel):
    source_id: str
    source_title: str
    source_roles: list[SourceRole]
    quote: str
    context: str


class AuditClaimInput(StrictModel):
    claim_id: str
    field: str
    field_definition: str
    normalized_claim: str
    evidence: list[AuditEvidenceContext]


class SemanticAuditInput(StrictModel):
    app_id: int
    app_name: str
    claims: list[AuditClaimInput]


class ClaimAuditResult(StrictModel):
    claim_id: str
    decision: AuditDecision
    reason: str = Field(min_length=1, max_length=500)


class SemanticAuditResponse(StrictModel):
    results: list[ClaimAuditResult]


class AdmissionChange(StrictModel):
    field: str
    old_value: object
    new_value: object
    decision: AuditDecision
    reason: str


class AdmissionReport(StrictModel):
    changes: list[AdmissionChange]


class RunMetrics(StrictModel):
    search_calls: int = 0
    fetch_calls: int = 0
    openai_calls: int = 0
    extraction_calls: int = 0
    audit_calls: int = 0
    browser_calls: int = 0
    search_latency_ms: int = 0
    fetch_latency_ms: int = 0
    openai_latency_ms: int = 0
    extraction_latency_ms: int = 0
    audit_latency_ms: int = 0
    total_latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    extraction_input_tokens: int = 0
    extraction_output_tokens: int = 0
    audit_input_tokens: int = 0
    audit_output_tokens: int = 0
    extraction_model: str = ""
    audit_model: str = ""
