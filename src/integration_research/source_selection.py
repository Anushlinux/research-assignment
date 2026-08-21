"""Field-specific GitHub search planning and official-source selection."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from integration_research.models import SourceRole, SourceTier

SearchIntent = SourceRole


@dataclass(frozen=True)
class SearchPlan:
    role: SourceRole
    query: str

    @property
    def intent(self) -> SourceRole:
        """Compatibility name for stored Milestone 1 search artifacts."""

        return self.role


SEARCH_PLANS: tuple[SearchPlan, ...] = (
    SearchPlan(
        SourceRole.AUTHENTICATION,
        'site:docs.github.com "GitHub" REST API authentication token OAuth app OAuth 2.0',
    ),
    SearchPlan(
        SourceRole.CREDENTIAL_ACCESS,
        'site:docs.github.com "GitHub" "personal access token" create token developer settings',
    ),
    SearchPlan(
        SourceRole.API_SURFACE,
        'site:docs.github.com "GitHub" REST GraphQL API overview documentation',
    ),
    SearchPlan(
        SourceRole.COMMERCIAL_OR_PRODUCTION_GATE,
        'site:docs.github.com "GitHub" API pricing plan app review approval production access',
    ),
    SearchPlan(SourceRole.MCP, '"GitHub" official MCP server'),
)


ROLE_TERMS: dict[SourceRole, tuple[str, ...]] = {
    SourceRole.AUTHENTICATION: (
        "authentication",
        "authenticate",
        "oauth",
        "token",
        "authorization",
    ),
    SourceRole.CREDENTIAL_ACCESS: (
        "create-token",
        "personal-access-token",
        "generate-token",
        "register-application",
        "developer-settings",
        "credentials",
    ),
    SourceRole.API_SURFACE: ("rest", "graphql", "api", "endpoint"),
    SourceRole.COMMERCIAL_OR_PRODUCTION_GATE: (
        "pricing",
        "plan",
        "review",
        "approval",
        "production",
    ),
    SourceRole.MCP: ("mcp", "model-context-protocol"),
}

CREDENTIAL_REWARDS: tuple[str, ...] = (
    "create token",
    "create-token",
    "personal access token",
    "personal-access-token",
    "generate token",
    "register application",
    "developer settings",
    "create integration",
    "obtain credentials",
    "generating-a-user-access-token",
    "user-access-token",
    "personal-access-tokens",
    "managing-private-keys",
)

IRRELEVANT_MARKETPLACE_TERMS: tuple[str, ...] = (
    "marketplace selling",
    "selling-your-app",
    "app listing",
    "revenue share",
    "pricing an app",
    "pricing-plans-for-github-marketplace-apps",
    "github-marketplace",
    "listing-an-app",
    "listing-on-github-marketplace",
    "requirements-for-listing",
    "setting-pricing-plans-for-your-listing",
    "testing-your-app",
)

MINIMUM_ROLE_SCORES: dict[SourceRole, int] = {
    SourceRole.AUTHENTICATION: 100,
    SourceRole.CREDENTIAL_ACCESS: 130,
    SourceRole.API_SURFACE: 100,
    SourceRole.COMMERCIAL_OR_PRODUCTION_GATE: 100,
    SourceRole.MCP: 100,
}


@dataclass(frozen=True)
class SearchCandidate:
    role: SourceRole
    query: str
    title: str
    url: str
    normalized_url: str
    search_position: int
    score: int
    reasons: tuple[str, ...]
    source_tier: SourceTier

    @property
    def intent(self) -> SourceRole:
        return self.role

    def as_dict(self) -> dict[str, object]:
        return {
            "source_role": self.role.value,
            "query": self.query,
            "title": self.title,
            "url": self.url,
            "normalized_url": self.normalized_url,
            "search_position": self.search_position,
            "score": self.score,
            "reasons": list(self.reasons),
            "source_tier": self.source_tier.value,
        }


def normalize_url(url: str) -> str:
    """Normalize a candidate URL without changing meaningful query parameters."""

    parsed = urlsplit(url.strip())
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if not scheme or not hostname:
        return url.strip()

    port = parsed.port
    netloc = hostname if port in {None, 443} else f"{hostname}:{port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=False)
            if not key.lower().startswith("utm_")
        )
    )
    return urlunsplit((scheme, netloc, path, query, ""))


def official_source_tier(url: str) -> SourceTier | None:
    """Return the deterministic GitHub source tier, or reject the URL."""

    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https":
        return None
    host = (parsed.hostname or "").lower()
    if host == "docs.github.com":
        return SourceTier.OFFICIAL_DEVELOPER_DOCS
    if host == "github.blog":
        return SourceTier.OFFICIAL_BLOG
    if host == "github.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0].lower() == "github":
            return SourceTier.OFFICIAL_GITHUB
    return None


def rank_candidate(
    *,
    role: SourceRole | None = None,
    intent: SourceRole | None = None,
    query: str,
    title: str,
    url: str,
    search_position: int,
) -> SearchCandidate | None:
    selected_role = role or intent
    if selected_role is None:
        raise ValueError("rank_candidate requires a source role")
    tier = official_source_tier(url)
    if tier is None:
        return None

    score = {
        SourceTier.OFFICIAL_DEVELOPER_DOCS: 100,
        SourceTier.OFFICIAL_GITHUB: 90,
        SourceTier.OFFICIAL_BLOG: 70,
    }[tier]
    reasons = [f"official source tier +{score}"]
    searchable = f"{title} {urlsplit(url).path}".lower().replace("_", "-")

    developer_paths = ("/docs/", "/rest", "/graphql", "/api", "/developer", "/apps")
    if any(term in searchable for term in developer_paths):
        score += 25
        reasons.append("developer or API documentation path +25")
    if any(term in searchable for term in ROLE_TERMS[selected_role]):
        score += 20
        reasons.append(f"{selected_role.value} role match +20")
    if selected_role == SourceRole.CREDENTIAL_ACCESS and any(
        term in searchable for term in CREDENTIAL_REWARDS
    ):
        score += 45
        reasons.append("credential creation evidence +45")
    if (
        selected_role == SourceRole.CREDENTIAL_ACCESS
        and "managing-your-personal-access-tokens" in searchable
    ):
        score += 70
        reasons.append("personal access token creation guide +70")
    if selected_role == SourceRole.CREDENTIAL_ACCESS and "permissions-required" in searchable:
        score -= 60
        reasons.append("permissions reference is not credential creation -60")
    if selected_role == SourceRole.API_SURFACE and urlsplit(url).path.rstrip("/").lower() in {
        "/en/rest",
        "/en/graphql",
    }:
        score += 30
        reasons.append("REST or GraphQL overview root +30")
    if any(term in searchable for term in IRRELEVANT_MARKETPLACE_TERMS):
        score -= 90
        reasons.append("irrelevant Marketplace selling page -90")
    if (
        selected_role == SourceRole.MCP
        and urlsplit(url).path.rstrip("/").lower() == "/github/github-mcp-server"
    ):
        score += 50
        reasons.append("official MCP repository root +50")
    if tier == SourceTier.OFFICIAL_BLOG or "/blog" in searchable:
        score -= 15
        reasons.append("blog penalty -15")
    if "community" in searchable or "forum" in searchable:
        score -= 40
        reasons.append("community or forum penalty -40")

    return SearchCandidate(
        role=selected_role,
        query=query,
        title=title.strip() or url,
        url=url,
        normalized_url=normalize_url(url),
        search_position=search_position,
        score=score,
        reasons=tuple(reasons),
        source_tier=tier,
    )


def candidates_from_citations(
    *,
    role: SourceRole | None = None,
    intent: SourceRole | None = None,
    query: str,
    citations: list[dict[str, object]],
) -> list[SearchCandidate]:
    selected_role = role or intent
    if selected_role is None:
        raise ValueError("candidates_from_citations requires a source role")
    candidates: list[SearchCandidate] = []
    for position, citation in enumerate(citations):
        title_value = citation.get("title", "")
        url_value = citation.get("url", "")
        if not isinstance(title_value, str) or not isinstance(url_value, str):
            continue
        candidate = rank_candidate(
            role=selected_role,
            query=query,
            title=title_value,
            url=url_value,
            search_position=position,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _sort_key(candidate: SearchCandidate) -> tuple[int, int, str]:
    return (-candidate.score, candidate.search_position, candidate.normalized_url)


def _meets_role_threshold(candidate: SearchCandidate) -> bool:
    if candidate.score < MINIMUM_ROLE_SCORES[candidate.role]:
        return False
    if candidate.role == SourceRole.COMMERCIAL_OR_PRODUCTION_GATE:
        searchable = f"{candidate.title} {urlsplit(candidate.url).path}".lower()
        return any(term in searchable for term in ROLE_TERMS[candidate.role])
    return True


def _api_family(candidate: SearchCandidate) -> str:
    path = urlsplit(candidate.normalized_url).path.lower()
    if path.startswith("/en/graphql"):
        return "graphql"
    if path.startswith("/en/rest"):
        return "rest"
    return "other"


def select_sources(candidates: list[SearchCandidate], *, maximum: int = 5) -> list[SearchCandidate]:
    """Select strong role coverage, then optionally a second API source."""

    selected: list[SearchCandidate] = []
    seen: set[str] = set()

    for plan in SEARCH_PLANS:
        role_candidates = sorted(
            (
                candidate
                for candidate in candidates
                if candidate.role == plan.role and _meets_role_threshold(candidate)
            ),
            key=_sort_key,
        )
        for candidate in role_candidates:
            if candidate.normalized_url not in seen:
                selected.append(candidate)
                seen.add(candidate.normalized_url)
                break
        if len(selected) >= maximum:
            return selected

    api_candidates = sorted(
        (
            candidate
            for candidate in candidates
            if candidate.role == SourceRole.API_SURFACE and _meets_role_threshold(candidate)
        ),
        key=_sort_key,
    )
    selected_api_families = {
        _api_family(candidate) for candidate in selected if candidate.role == SourceRole.API_SURFACE
    }
    diverse_api_candidates = sorted(
        api_candidates,
        key=lambda candidate: (
            _api_family(candidate) in selected_api_families,
            *_sort_key(candidate),
        ),
    )
    for candidate in diverse_api_candidates:
        if candidate.normalized_url in seen:
            continue
        selected.append(candidate)
        seen.add(candidate.normalized_url)
        if len(selected) >= maximum:
            return selected

    for candidate in sorted(candidates, key=_sort_key):
        if not _meets_role_threshold(candidate) or candidate.normalized_url in seen:
            continue
        selected.append(candidate)
        seen.add(candidate.normalized_url)
        if len(selected) >= maximum:
            break
    return selected
