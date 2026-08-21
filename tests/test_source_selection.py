from integration_research.models import SourceRole, SourceTier
from integration_research.source_selection import (
    SEARCH_PLANS,
    normalize_url,
    official_source_tier,
    rank_candidate,
    select_sources,
)


def test_official_host_validation_rejects_lookalikes_and_community_repos() -> None:
    assert (
        official_source_tier("https://docs.github.com/en/rest")
        == SourceTier.OFFICIAL_DEVELOPER_DOCS
    )
    assert (
        official_source_tier("https://github.com/github/github-mcp-server")
        == SourceTier.OFFICIAL_GITHUB
    )
    assert official_source_tier("https://github.com/someone/github-mcp") is None
    assert official_source_tier("https://docs.github.com.evil.example/rest") is None
    assert official_source_tier("http://docs.github.com/rest") is None


def test_normalize_url_removes_tracking_fragment_and_default_port() -> None:
    assert normalize_url("HTTPS://DOCS.GITHUB.COM:443/en/rest/?utm_source=x#part") == (
        "https://docs.github.com/en/rest"
    )


def test_rank_and_select_cover_five_roles_deterministically() -> None:
    urls = {
        SourceRole.AUTHENTICATION: "https://docs.github.com/en/rest/authentication",
        SourceRole.CREDENTIAL_ACCESS: (
            "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/"
            "managing-your-personal-access-tokens"
        ),
        SourceRole.API_SURFACE: "https://docs.github.com/en/rest/about-the-rest-api",
        SourceRole.COMMERCIAL_OR_PRODUCTION_GATE: (
            "https://docs.github.com/en/get-started/learning-about-github/types-of-github-accounts"
        ),
        SourceRole.MCP: "https://github.com/github/github-mcp-server",
    }
    candidates = []
    for plan in SEARCH_PLANS:
        candidate = rank_candidate(
            role=plan.role,
            query=plan.query,
            title=(
                "Production approval pricing"
                if plan.role == SourceRole.COMMERCIAL_OR_PRODUCTION_GATE
                else plan.role.value
            ),
            url=urls[plan.role],
            search_position=0,
        )
        assert candidate is not None
        candidates.append(candidate)

    selected = select_sources(candidates, maximum=5)
    assert len(selected) == 5
    assert [candidate.role for candidate in selected] == [plan.role for plan in SEARCH_PLANS]
    assert len({candidate.normalized_url for candidate in selected}) == 5


def test_marketplace_selling_page_loses_to_credential_creation_page() -> None:
    query = next(plan.query for plan in SEARCH_PLANS if plan.role == SourceRole.CREDENTIAL_ACCESS)
    marketplace = rank_candidate(
        role=SourceRole.CREDENTIAL_ACCESS,
        query=query,
        title="Pricing plans for GitHub Marketplace apps",
        url=(
            "https://docs.github.com/en/apps/github-marketplace/selling-your-app-on-"
            "github-marketplace/pricing-plans-for-github-marketplace-apps"
        ),
        search_position=0,
    )
    credentials = rank_candidate(
        role=SourceRole.CREDENTIAL_ACCESS,
        query=query,
        title="Managing your personal access tokens",
        url=(
            "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/"
            "managing-your-personal-access-tokens"
        ),
        search_position=3,
    )
    assert marketplace is not None and credentials is not None
    assert credentials.score > marketplace.score
    assert select_sources([marketplace, credentials], maximum=1) == [credentials]


def test_docs_rank_above_blog_and_search_position_breaks_ties() -> None:
    plan = SEARCH_PLANS[0]
    first = rank_candidate(
        role=plan.role,
        query=plan.query,
        title="Authentication",
        url="https://docs.github.com/en/rest/authentication/one",
        search_position=0,
    )
    second = rank_candidate(
        role=plan.role,
        query=plan.query,
        title="Authentication",
        url="https://docs.github.com/en/rest/authentication/two",
        search_position=1,
    )
    blog = rank_candidate(
        role=plan.role,
        query=plan.query,
        title="Authentication blog",
        url="https://github.blog/authentication",
        search_position=0,
    )
    assert first is not None and second is not None and blog is not None
    assert select_sources([second, blog, first], maximum=1) == [first]
