"""Catalog-derived search planning and deterministic trusted-source selection."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from integration_research.models import AppInput, SourceRole, SourceTier

SearchIntent = SourceRole


@dataclass(frozen=True)
class SearchPlan:
    role: SourceRole
    query: str

    @property
    def intent(self) -> SourceRole:
        return self.role


@dataclass(frozen=True)
class TrustedSourcePolicy:
    """Trusted URL seeds derived only from the canonical app catalog."""

    seed_urls: tuple[str, ...]
    seed_hosts: tuple[str, ...]
    required_path_prefixes: tuple[str, ...]
    app_name: str

    def trusts_host(self, host: str) -> bool:
        normalized = host.lower().rstrip(".")
        return any(
            normalized == seed or normalized.endswith(f".{seed}") for seed in self.seed_hosts
        )

    def trusts_url(self, url: str) -> bool:
        parsed = urlsplit(url)
        if parsed.scheme.lower() != "https" or not self.trusts_host(parsed.hostname or ""):
            return False
        if not self.required_path_prefixes:
            return True
        path = parsed.path.rstrip("/").lower()
        return any(
            path == prefix or path.startswith(f"{prefix}/")
            for prefix in self.required_path_prefixes
        )


ROLE_ORDER: tuple[SourceRole, ...] = (
    SourceRole.AUTHENTICATION,
    SourceRole.CREDENTIAL_ACCESS,
    SourceRole.API_SURFACE,
    SourceRole.COMMERCIAL_OR_PRODUCTION_GATE,
    SourceRole.MCP,
)

ROLE_QUERY_TERMS: dict[SourceRole, str] = {
    SourceRole.AUTHENTICATION: "developer API authentication OAuth token API key service account",
    SourceRole.CREDENTIAL_ACCESS: (
        "developer credentials create key token signup self serve administrator access"
    ),
    SourceRole.COMMERCIAL_OR_PRODUCTION_GATE: (
        "API pricing production approval app review partner admin contact sales"
    ),
    SourceRole.API_SURFACE: "developer API REST GraphQL RPC CLI SDK webhooks endpoints",
    SourceRole.MCP: 'MCP "Model Context Protocol" agent callable CLI server',
}

ROLE_TERMS: dict[SourceRole, tuple[str, ...]] = {
    SourceRole.AUTHENTICATION: (
        "authentication",
        "authenticate",
        "oauth",
        "token",
        "authorization",
        "api-key",
    ),
    SourceRole.CREDENTIAL_ACCESS: (
        "create-token",
        "generate-token",
        "register-application",
        "developer-settings",
        "credentials",
        "api-key",
        "access-key",
    ),
    SourceRole.API_SURFACE: (
        "rest",
        "graphql",
        "rpc",
        "api",
        "endpoint",
        "cli",
        "webhook",
    ),
    SourceRole.COMMERCIAL_OR_PRODUCTION_GATE: (
        "pricing",
        "plan",
        "review",
        "approval",
        "production",
        "partner",
        "sales",
        "admin",
    ),
    SourceRole.MCP: ("mcp", "model-context-protocol", "model context protocol"),
}

MINIMUM_ROLE_SCORES: dict[SourceRole, int] = {role: 90 for role in ROLE_ORDER}

# On shared code forges, the hostname alone does not identify an official project. An owner and
# repository path is therefore a trust boundary. Ordinary documentation hints use their paths only
# as ranking signals so other pages on the trusted host and its subdomains remain eligible.
SHARED_REPOSITORY_HOST_PATTERN = re.compile(
    r"^(?:git(?:hub|lab)\.com|bitbucket\.org|codeberg\.org)$"
)


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


def _as_https_url(value: str) -> str | None:
    candidate = value.strip().rstrip(".,;)")
    if not candidate:
        return None
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    return normalize_url(urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, "")))


def derive_trusted_source_policy(app: AppInput) -> TrustedSourcePolicy:
    """Derive the complete trust boundary from URL-like catalog fields, never model output."""

    values = [app.website_hint]
    seed_urls = tuple(dict.fromkeys(url for value in values if (url := _as_https_url(value))))
    seed_hosts = tuple(dict.fromkeys((urlsplit(url).hostname or "").lower() for url in seed_urls))
    required_path_prefixes: list[str] = []
    for url in seed_urls:
        parsed = urlsplit(url)
        parts = [part for part in parsed.path.split("/") if part]
        host = (parsed.hostname or "").lower()
        if SHARED_REPOSITORY_HOST_PATTERN.fullmatch(host) and len(parts) >= 2:
            required_path_prefixes.append("/" + "/".join(part.lower() for part in parts[:2]))
    return TrustedSourcePolicy(
        seed_urls=seed_urls,
        seed_hosts=seed_hosts,
        required_path_prefixes=tuple(dict.fromkeys(required_path_prefixes)),
        app_name=app.app_name,
    )


def build_search_plans(
    app: AppInput, policy: TrustedSourcePolicy | None = None
) -> tuple[SearchPlan, ...]:
    selected_policy = policy or derive_trusted_source_policy(app)
    sites = " OR ".join(f"site:{host}" for host in selected_policy.seed_hosts)
    identity = f'"{app.app_name}" {app.category}'
    hint = app.website_hint
    notes = app.notes
    prefix = " ".join(part for part in (sites, identity, hint, notes) if part)
    return tuple(
        SearchPlan(role=role, query=f"{prefix} {ROLE_QUERY_TERMS[role]}".strip())
        for role in ROLE_ORDER
    )


def official_source_tier(url: str, policy: TrustedSourcePolicy) -> SourceTier | None:
    """Classify a fetched URL only when the catalog-derived policy trusts it."""

    if not policy.trusts_url(url):
        return None
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    searchable = f"{host} {path}"
    if "pricing" in searchable or "/plans" in path:
        return SourceTier.OFFICIAL_PRICING
    if any(term in searchable for term in ("help.", "support.", "/help", "/support")):
        return SourceTier.OFFICIAL_HELP
    if "blog." in searchable or "/blog" in path:
        return SourceTier.OFFICIAL_BLOG
    if any(
        term in searchable
        for term in ("docs.", "developer.", "developers.", "api.", "/docs", "/api", "/rest")
    ):
        return SourceTier.OFFICIAL_DEVELOPER_DOCS
    return SourceTier.OFFICIAL_WEBSITE


def rank_candidate(
    *,
    policy: TrustedSourcePolicy,
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
    tier = official_source_tier(url, policy)
    if tier is None:
        return None
    tier_scores = {
        SourceTier.OFFICIAL_DEVELOPER_DOCS: 100,
        SourceTier.OFFICIAL_REPOSITORY: 95,
        SourceTier.OFFICIAL_HELP: 80,
        SourceTier.OFFICIAL_PRICING: 85,
        SourceTier.OFFICIAL_BLOG: 65,
        SourceTier.OFFICIAL_WEBSITE: 70,
    }
    score = tier_scores[tier]
    reasons = [f"trusted source tier +{score}"]
    normalized = normalize_url(url)
    searchable = f"{title} {urlsplit(url).path}".lower().replace("_", "-")
    candidate_path = [part.lower() for part in urlsplit(normalized).path.split("/") if part]
    seed_paths = [
        [part.lower() for part in urlsplit(seed).path.split("/") if part]
        for seed in policy.seed_urls
    ]
    if (
        any(
            candidate_path == seed_path or candidate_path[: len(seed_path)] == seed_path
            for seed_path in seed_paths
            if seed_path
        )
        or normalized in policy.seed_urls
    ):
        score += 60
        reasons.append("catalog hint URL or descendant path +60")
    elif any(
        all(token in candidate_path for token in seed_path) for seed_path in seed_paths if seed_path
    ):
        score += 45
        reasons.append("catalog hint path token affinity +45")
    elif any(seed_path for seed_path in seed_paths) and policy.app_name.lower() not in (
        f"{title} {urlsplit(normalized).hostname or ''} {urlsplit(normalized).path}".lower()
    ):
        score -= 80
        reasons.append("same trusted host but unrelated product path -80")
    if any(term in searchable for term in ROLE_TERMS[selected_role]):
        score += 30
        reasons.append(f"{selected_role.value} role match +30")
    if any(term in searchable for term in ("/docs", "/developer", "/api", "/rest")):
        score += 20
        reasons.append("developer documentation path +20")
    if tier == SourceTier.OFFICIAL_BLOG:
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
        normalized_url=normalized,
        search_position=search_position,
        score=score,
        reasons=tuple(reasons),
        source_tier=tier,
    )


def candidates_from_citations(
    *,
    policy: TrustedSourcePolicy,
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
        title = citation.get("title", "")
        url = citation.get("url", "")
        if not isinstance(title, str) or not isinstance(url, str):
            continue
        candidate = rank_candidate(
            policy=policy,
            role=selected_role,
            query=query,
            title=title,
            url=url,
            search_position=position,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def candidates_from_trusted_seeds(
    *,
    app: AppInput,
    policy: TrustedSourcePolicy,
    plans: tuple[SearchPlan, ...],
) -> list[SearchCandidate]:
    """Treat catalog-provided URLs as deterministic candidates when search omits them."""

    candidates: list[SearchCandidate] = []
    title = " ".join(
        part for part in (app.app_name, app.category, app.website_hint, app.notes) if part
    )
    for plan in plans:
        for seed_url in policy.seed_urls:
            candidate = rank_candidate(
                policy=policy,
                role=plan.role,
                query=plan.query,
                title=title,
                url=seed_url,
                search_position=-1,
            )
            if candidate is not None:
                candidates.append(
                    replace(
                        candidate,
                        score=candidate.score - 50,
                        reasons=(*candidate.reasons, "catalog seed fallback -50"),
                    )
                )
    return candidates


def _sort_key(candidate: SearchCandidate) -> tuple[int, int, str]:
    return (-candidate.score, candidate.search_position, candidate.normalized_url)


def _meets_role_threshold(candidate: SearchCandidate) -> bool:
    if candidate.score < MINIMUM_ROLE_SCORES[candidate.role]:
        return False
    searchable = f"{candidate.title} {urlsplit(candidate.url).path}".lower().replace("_", "-")
    return any(term in searchable for term in ROLE_TERMS[candidate.role])


def select_sources(candidates: list[SearchCandidate], *, maximum: int = 5) -> list[SearchCandidate]:
    """Select the best candidate independently for each role.

    The same URL may be returned for multiple roles. The pipeline preserves those assignments and
    deduplicates only the network fetch.
    """

    selected: list[SearchCandidate] = []
    for role in ROLE_ORDER:
        role_candidates = sorted(
            (
                candidate
                for candidate in candidates
                if candidate.role == role and _meets_role_threshold(candidate)
            ),
            key=_sort_key,
        )
        if role_candidates:
            selected.append(role_candidates[0])
        if len(selected) >= maximum:
            return selected
    return selected
