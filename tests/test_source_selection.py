from integration_research.models import AppInput, SourceRole, SourceTier
from integration_research.source_selection import (
    ROLE_ORDER,
    build_search_plans,
    build_targeted_search_plan,
    candidates_from_trusted_seeds,
    derive_trusted_source_policy,
    normalize_url,
    official_source_tier,
    rank_candidate,
    select_sources,
)


def app(app_id: int, name: str, hint: str, category: str = "Productivity") -> AppInput:
    return AppInput(
        app_id=app_id,
        app_name=name,
        website_hint=hint,
        category=category,
        notes="catalog note",
    )


def test_trusted_hosts_accept_subdomains_and_reject_lookalikes() -> None:
    policy = derive_trusted_source_policy(app(22, "Messaging Product", "vendor.test/docs"))
    assert policy.trusts_url("https://vendor.test/api")
    assert policy.trusts_url("https://docs.vendor.test/api")
    assert not policy.trusts_url("https://vendor.test.evil.example/api")
    assert not policy.trusts_url("https://evilvendor.test/api")
    assert not policy.trusts_url("http://vendor.test/api")
    assert official_source_tier("https://docs.vendor.test/api", policy) == (
        SourceTier.OFFICIAL_DEVELOPER_DOCS
    )


def test_documentation_hint_path_is_ranking_context_not_a_trust_boundary() -> None:
    policy = derive_trusted_source_policy(
        app(40, "Commerce Product", "commerce.test/document/rest-api")
    )
    assert policy.required_path_prefixes == ()
    assert policy.trusts_url("https://commerce.test/oauth/authentication")
    assert policy.trusts_url("https://developer.commerce.test/reference/orders")


def test_repository_hint_preserves_owner_and_repository_scope() -> None:
    policy = derive_trusted_source_policy(
        app(98, "Diagram CLI", "github.com/example-org/diagram-cli")
    )
    assert policy.seed_urls == ("https://github.com/example-org/diagram-cli",)
    assert policy.required_path_prefixes == ("/example-org/diagram-cli",)
    assert policy.trusts_url("https://github.com/example-org/diagram-cli/tree/main/docs")
    assert not policy.trusts_url("https://github.com/unrelated/diagram-cli")


def test_queries_are_generic_metadata_driven_and_cover_every_role() -> None:
    first = app(1, "Alpha Product", "alpha.example/docs", "CRM")
    second = app(2, "Beta Product", "beta.example/developers", "Finance")
    first_plans = build_search_plans(first)
    second_plans = build_search_plans(second)
    assert tuple(plan.role for plan in first_plans) == ROLE_ORDER
    assert all("Alpha Product" in plan.query for plan in first_plans)
    assert all("alpha.example/docs" in plan.query for plan in first_plans)
    assert all("catalog note" in plan.query for plan in first_plans)
    assert {plan.query for plan in first_plans}.isdisjoint({plan.query for plan in second_plans})


def test_hinted_path_gets_strongest_ranking_signal() -> None:
    catalog_app = app(31, "Ads Product", "developers.example/ads")
    policy = derive_trusted_source_policy(catalog_app)
    query = build_search_plans(catalog_app)[0].query
    hinted = rank_candidate(
        policy=policy,
        role=SourceRole.AUTHENTICATION,
        query=query,
        title="Authentication",
        url="https://developers.example/ads/authentication",
        search_position=2,
    )
    unrelated_path = rank_candidate(
        policy=policy,
        role=SourceRole.AUTHENTICATION,
        query=query,
        title="Authentication",
        url="https://developers.example/another-product/authentication",
        search_position=0,
    )
    assert hinted is not None and unrelated_path is not None
    assert hinted.score > unrelated_path.score
    assert "unrelated product path" in " ".join(unrelated_path.reasons)


def test_catalog_seed_can_recover_a_search_omitted_local_cli() -> None:
    catalog_app = AppInput(
        app_id=98,
        app_name="Diagram CLI",
        website_hint="code.example/diagram/cli",
        category="Developer tools",
        notes="Open-source command line renderer",
    )
    policy = derive_trusted_source_policy(catalog_app)
    candidates = candidates_from_trusted_seeds(
        app=catalog_app,
        policy=policy,
        plans=build_search_plans(catalog_app, policy),
    )
    selected = select_sources(candidates, maximum=5)
    assert [candidate.role for candidate in selected] == [SourceRole.API_SURFACE]
    assert selected[0].normalized_url == "https://code.example/diagram/cli"


def test_rank_and_select_cover_roles_deterministically() -> None:
    catalog_app = app(10, "Generic Product", "docs.generic.example")
    policy = derive_trusted_source_policy(catalog_app)
    candidates = []
    for index, plan in enumerate(build_search_plans(catalog_app)):
        candidate = rank_candidate(
            policy=policy,
            role=plan.role,
            query=plan.query,
            title=f"{plan.role.value} authentication credentials pricing API MCP",
            url=f"https://docs.generic.example/api/{plan.role.value}",
            search_position=index,
        )
        assert candidate is not None
        candidates.append(candidate)
    selected = select_sources(candidates, maximum=5)
    assert [candidate.role for candidate in selected] == list(ROLE_ORDER)


def test_same_url_can_be_selected_for_multiple_roles() -> None:
    catalog_app = app(10, "Generic Product", "docs.generic.example")
    policy = derive_trusted_source_policy(catalog_app)
    shared_url = "https://docs.generic.example/api/authentication-credentials"
    candidates = []
    for role in (SourceRole.AUTHENTICATION, SourceRole.CREDENTIAL_ACCESS):
        candidate = rank_candidate(
            policy=policy,
            role=role,
            query="generic query",
            title="API authentication credentials token",
            url=shared_url,
            search_position=0,
        )
        assert candidate is not None
        candidates.append(candidate)
    selected = select_sources(candidates, maximum=5)
    assert [candidate.role for candidate in selected] == [
        SourceRole.AUTHENTICATION,
        SourceRole.CREDENTIAL_ACCESS,
    ]
    assert len({candidate.normalized_url for candidate in selected}) == 1


def test_two_distinct_pages_are_selected_for_each_critical_role() -> None:
    catalog_app = app(10, "Generic Product", "docs.generic.example")
    policy = derive_trusted_source_policy(catalog_app)
    candidates = []
    for role in ROLE_ORDER:
        count = (
            2
            if role
            in {
                SourceRole.AUTHENTICATION,
                SourceRole.CREDENTIAL_ACCESS,
                SourceRole.API_SURFACE,
            }
            else 1
        )
        for index in range(count):
            candidate = rank_candidate(
                policy=policy,
                role=role,
                query="generic query",
                title=f"{role.value} authentication credentials API endpoint pricing MCP",
                url=f"https://docs.generic.example/api/{role.value}/{index}",
                search_position=index,
            )
            assert candidate is not None
            candidates.append(candidate)

    selected = select_sources(candidates, maximum=8)

    assert len(selected) == 8
    for role in (
        SourceRole.AUTHENTICATION,
        SourceRole.CREDENTIAL_ACCESS,
        SourceRole.API_SURFACE,
    ):
        assert len({item.normalized_url for item in selected if item.role == role}) == 2


def test_targeted_recovery_query_is_catalog_anchored() -> None:
    catalog_app = app(4, "Attio", "attio.com")
    plan = build_targeted_search_plan(catalog_app, "auth_methods")

    assert plan.role == SourceRole.AUTHENTICATION
    assert "site:attio.com" in plan.query
    assert '"Attio"' in plan.query
    assert "authorization code" in plan.query


def test_root_domain_queries_include_probable_developer_subdomains() -> None:
    catalog_app = app(6, "Podio", "podio.com")
    plan = build_targeted_search_plan(catalog_app, "api_availability")

    assert "site:podio.com" in plan.query
    assert "site:developers.podio.com" in plan.query
    assert "site:docs.podio.com" in plan.query


def test_normalize_url_removes_tracking_fragment_and_default_port() -> None:
    assert normalize_url("HTTPS://DOCS.EXAMPLE.COM:443/api/?utm_source=x#part") == (
        "https://docs.example.com/api"
    )
