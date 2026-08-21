from integration_research.models import SourceTier
from integration_research.source_selection import (
    SEARCH_PLANS,
    SearchIntent,
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


def test_rank_and_select_cover_intents_deterministically() -> None:
    candidates = []
    urls = {
        SearchIntent.AUTH: "https://docs.github.com/en/rest/authentication",
        SearchIntent.ACCESS: "https://docs.github.com/en/authentication/managing-tokens",
        SearchIntent.SURFACE: "https://docs.github.com/en/rest/about-the-rest-api",
        SearchIntent.MCP: "https://github.com/github/github-mcp-server",
    }
    for plan in SEARCH_PLANS:
        candidate = rank_candidate(
            intent=plan.intent,
            query=plan.query,
            title=plan.intent.value,
            url=urls[plan.intent],
            search_position=0,
        )
        assert candidate is not None
        candidates.append(candidate)

    duplicate = rank_candidate(
        intent=SearchIntent.SURFACE,
        query="duplicate",
        title="REST API",
        url=urls[SearchIntent.AUTH],
        search_position=5,
    )
    assert duplicate is not None
    candidates.append(duplicate)

    selected = select_sources(candidates, maximum=4)
    assert len(selected) == 4
    assert [candidate.intent for candidate in selected] == [
        SearchIntent.AUTH,
        SearchIntent.ACCESS,
        SearchIntent.SURFACE,
        SearchIntent.MCP,
    ]
    assert len({candidate.normalized_url for candidate in selected}) == 4


def test_docs_rank_above_blog_and_search_position_breaks_ties() -> None:
    plan = SEARCH_PLANS[0]
    first = rank_candidate(
        intent=plan.intent,
        query=plan.query,
        title="Authentication",
        url="https://docs.github.com/en/rest/authentication/one",
        search_position=0,
    )
    second = rank_candidate(
        intent=plan.intent,
        query=plan.query,
        title="Authentication",
        url="https://docs.github.com/en/rest/authentication/two",
        search_position=1,
    )
    blog = rank_candidate(
        intent=plan.intent,
        query=plan.query,
        title="Authentication blog",
        url="https://github.blog/authentication",
        search_position=0,
    )
    assert first is not None and second is not None and blog is not None
    assert select_sources([second, blog, first], maximum=1) == [first]
