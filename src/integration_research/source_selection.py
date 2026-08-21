"""Deterministic GitHub search planning and official-source selection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from integration_research.models import SourceTier


class SearchIntent(StrEnum):
    AUTH = "api_authentication"
    ACCESS = "developer_access"
    SURFACE = "api_surface"
    MCP = "mcp"


@dataclass(frozen=True)
class SearchPlan:
    intent: SearchIntent
    query: str


SEARCH_PLANS: tuple[SearchPlan, ...] = (
    SearchPlan(
        SearchIntent.AUTH,
        'site:docs.github.com "GitHub" API authentication OAuth API key token',
    ),
    SearchPlan(
        SearchIntent.ACCESS,
        'site:docs.github.com "GitHub" developer credentials access pricing trial approval',
    ),
    SearchPlan(
        SearchIntent.SURFACE,
        'site:docs.github.com "GitHub" REST GraphQL API documentation',
    ),
    SearchPlan(SearchIntent.MCP, '"GitHub" official MCP server'),
)


INTENT_TERMS: dict[SearchIntent, tuple[str, ...]] = {
    SearchIntent.AUTH: ("authentication", "authenticate", "oauth", "token", "api-key"),
    SearchIntent.ACCESS: ("credential", "access", "pricing", "trial", "approval"),
    SearchIntent.SURFACE: ("rest", "graphql", "api", "webhook", "endpoint"),
    SearchIntent.MCP: ("mcp", "model-context-protocol"),
}


@dataclass(frozen=True)
class SearchCandidate:
    intent: SearchIntent
    query: str
    title: str
    url: str
    normalized_url: str
    search_position: int
    score: int
    reasons: tuple[str, ...]
    source_tier: SourceTier

    def as_dict(self) -> dict[str, object]:
        return {
            "intent": self.intent.value,
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
    intent: SearchIntent,
    query: str,
    title: str,
    url: str,
    search_position: int,
) -> SearchCandidate | None:
    tier = official_source_tier(url)
    if tier is None:
        return None

    score = {
        SourceTier.OFFICIAL_DEVELOPER_DOCS: 100,
        SourceTier.OFFICIAL_GITHUB: 90,
        SourceTier.OFFICIAL_BLOG: 70,
    }[tier]
    reasons = [f"official source tier +{score}"]
    searchable = f"{title} {urlsplit(url).path}".lower()

    developer_paths = ("/docs/", "/rest", "/graphql", "/api", "/developer", "/apps")
    if any(term in searchable for term in developer_paths):
        score += 25
        reasons.append("developer or API documentation path +25")
    if any(term in searchable for term in INTENT_TERMS[intent]):
        score += 20
        reasons.append(f"{intent.value} intent match +20")
    if tier == SourceTier.OFFICIAL_BLOG or "/blog" in searchable:
        score -= 15
        reasons.append("blog penalty -15")
    if "community" in searchable or "forum" in searchable:
        score -= 40
        reasons.append("community or forum penalty -40")

    return SearchCandidate(
        intent=intent,
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
    *, intent: SearchIntent, query: str, citations: list[dict[str, object]]
) -> list[SearchCandidate]:
    candidates: list[SearchCandidate] = []
    for position, citation in enumerate(citations):
        title_value = citation.get("title", "")
        url_value = citation.get("url", "")
        if not isinstance(title_value, str) or not isinstance(url_value, str):
            continue
        candidate = rank_candidate(
            intent=intent,
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


def select_sources(candidates: list[SearchCandidate], *, maximum: int = 4) -> list[SearchCandidate]:
    """Select one source per intent first, then fill from the overall ranking."""

    selected: list[SearchCandidate] = []
    seen: set[str] = set()

    for plan in SEARCH_PLANS:
        intent_candidates = sorted(
            (candidate for candidate in candidates if candidate.intent == plan.intent),
            key=_sort_key,
        )
        for candidate in intent_candidates:
            if candidate.normalized_url not in seen:
                selected.append(candidate)
                seen.add(candidate.normalized_url)
                break
        if len(selected) >= maximum:
            return selected

    for candidate in sorted(candidates, key=_sort_key):
        if candidate.normalized_url in seen:
            continue
        selected.append(candidate)
        seen.add(candidate.normalized_url)
        if len(selected) >= maximum:
            break
    return selected
