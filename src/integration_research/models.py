"""Strict data contracts for the Milestone 1.1 GitHub research path."""

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


class SourceTier(StrEnum):
    OFFICIAL_DEVELOPER_DOCS = "official_developer_docs"
    OFFICIAL_GITHUB = "official_github"
    OFFICIAL_BLOG = "official_blog"


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
    source_id: str = Field(pattern=r"^source_[1-5]$")
    snippet_id: str = Field(pattern=r"^source_[1-5]_snippet_[0-9]{3}$")


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
            if self.evidence:
                raise ValueError("unknown authentication must not carry evidence")
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
        auth_values = [item.method for item in self.auth_methods]
        if len(set(auth_values)) != len(auth_values):
            raise ValueError("auth_methods contains duplicate values")
        if AuthMethod.UNKNOWN in auth_values and len(auth_values) > 1:
            raise ValueError("unknown authentication cannot coexist with confirmed methods")

        style_values = [claim.value for claim in self.api_styles]
        if len(set(style_values)) != len(style_values):
            raise ValueError("api_styles contains duplicate values")
        return self


class ResolvedEvidence(StrictModel):
    source_id: str
    url: str
    title: str
    source_tier: SourceTier
    source_role: SourceRole
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
    snippet_id: str = Field(pattern=r"^source_[1-5]_snippet_[0-9]{3}$")
    source_id: str = Field(pattern=r"^source_[1-5]$")
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
    source_role: SourceRole
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
