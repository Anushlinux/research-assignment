"""Strict data contracts for the Milestone 1 GitHub research path."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base model that refuses fields outside the documented contract."""

    model_config = ConfigDict(extra="forbid")


class AuthMethod(StrEnum):
    OAUTH2 = "oauth2"
    OAUTH1 = "oauth1"
    API_KEY = "api_key"
    BASIC = "basic"
    BEARER_TOKEN = "bearer_token"
    PERSONAL_ACCESS_TOKEN = "personal_access_token"
    SERVICE_ACCOUNT = "service_account"
    JWT = "jwt"
    SIGNED_REQUEST = "signed_request"
    SESSION_COOKIE = "session_cookie"
    NONE = "none"
    OTHER = "other"
    UNKNOWN = "unknown"


class DeveloperAccess(StrEnum):
    SELF_SERVE_FREE = "self_serve_free"
    SELF_SERVE_TRIAL = "self_serve_trial"
    SELF_SERVE_PAID = "self_serve_paid"
    ADMIN_REQUIRED = "admin_required"
    VENDOR_REVIEW = "vendor_review"
    PARTNER_ONLY = "partner_only"
    CONTACT_SALES = "contact_sales"
    NOT_AVAILABLE = "not_available"
    UNKNOWN = "unknown"


class ProductionGate(StrEnum):
    NONE = "none"
    PAID_PLAN = "paid_plan"
    APP_REVIEW = "app_review"
    ADMIN_APPROVAL = "admin_approval"
    VENDOR_APPROVAL = "vendor_approval"
    PARTNER_APPROVAL = "partner_approval"
    CONTACT_SALES = "contact_sales"
    CUSTOMER_ACCOUNT_REQUIRED = "customer_account_required"
    UNKNOWN = "unknown"


class ApiAvailability(StrEnum):
    YES = "yes"
    LIMITED = "limited"
    NO = "no"
    UNKNOWN = "unknown"


class ApiProtocol(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"
    SOAP = "soap"
    RPC = "rpc"
    WEBSOCKET = "websocket"
    WEBHOOK = "webhook"
    CLI = "cli"
    SDK_ONLY = "sdk_only"
    OTHER = "other"
    UNKNOWN = "unknown"


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


class EvidenceRef(StrictModel):
    source_id: str = Field(pattern=r"^source_[1-4]$")
    quote: str = Field(min_length=1, max_length=500)


class Claim[ValueT](StrictModel):
    value: ValueT
    evidence: list[EvidenceRef]


class ApiCapabilitiesDraft(StrictModel):
    read: Claim[Ternary]
    write: Claim[Ternary]
    webhooks_or_events: Claim[Ternary]


class AppResearchDraft(StrictModel):
    app_id: int
    app_name: str
    category: str
    description: Claim[str]
    auth_methods: list[Claim[AuthMethod]] = Field(min_length=1)
    developer_access: Claim[DeveloperAccess]
    production_gates: list[Claim[ProductionGate]] = Field(min_length=1)
    api_availability: Claim[ApiAvailability]
    api_protocols: list[Claim[ApiProtocol]]
    api_breadth: Claim[ApiBreadth]
    api_capabilities: ApiCapabilitiesDraft
    api_surface_summary: Claim[str]
    mcp_status: Claim[McpStatus]
    blocker: Claim[str] | None
    unresolved_questions: list[str]

    @model_validator(mode="after")
    def validate_enum_collections(self) -> AppResearchDraft:
        auth_values = [claim.value for claim in self.auth_methods]
        if len(set(auth_values)) != len(auth_values):
            raise ValueError("auth_methods contains duplicate values")
        if AuthMethod.UNKNOWN in auth_values and len(auth_values) > 1:
            raise ValueError("unknown authentication cannot coexist with confirmed methods")

        gate_values = [claim.value for claim in self.production_gates]
        if len(set(gate_values)) != len(gate_values):
            raise ValueError("production_gates contains duplicate values")
        if ProductionGate.NONE in gate_values and len(gate_values) > 1:
            raise ValueError("the none production gate must appear alone")
        return self


class ResolvedEvidence(StrictModel):
    source_id: str
    url: str
    title: str
    source_tier: SourceTier
    quote: str
    retrieved_at: datetime
    content_hash: str


class ResolvedClaim[ValueT](StrictModel):
    value: ValueT
    evidence: list[ResolvedEvidence]


class ApiCapabilitiesFinal(StrictModel):
    read: ResolvedClaim[Ternary]
    write: ResolvedClaim[Ternary]
    webhooks_or_events: ResolvedClaim[Ternary]


class FinalAppResearch(StrictModel):
    app_id: int
    app_name: str
    website_hint: str
    category: str
    official_domains: list[str]
    description: ResolvedClaim[str]
    auth_methods: list[ResolvedClaim[AuthMethod]]
    developer_access: ResolvedClaim[DeveloperAccess]
    production_gates: list[ResolvedClaim[ProductionGate]]
    api_availability: ResolvedClaim[ApiAvailability]
    api_protocols: list[ResolvedClaim[ApiProtocol]]
    api_breadth: ResolvedClaim[ApiBreadth]
    api_capabilities: ApiCapabilitiesFinal
    api_surface_summary: ResolvedClaim[str]
    mcp_status: ResolvedClaim[McpStatus]
    blocker: ResolvedClaim[str] | None
    unresolved_questions: list[str]
    buildability: Buildability
    integration_paths: list[str]
    generated_at: datetime
    model: str
    pipeline_version: str
    prompt_version: str


class AppInput(StrictModel):
    app_id: int
    app_name: str
    website_hint: str
    category: str
    notes: str


class FetchedSource(StrictModel):
    source_id: str
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


class RunMetrics(StrictModel):
    search_calls: int = 0
    fetch_calls: int = 0
    openai_calls: int = 0
    browser_calls: int = 0
    search_latency_ms: int = 0
    fetch_latency_ms: int = 0
    openai_latency_ms: int = 0
    total_latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
