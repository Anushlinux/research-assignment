from integration_research.reduction import (
    build_evidence_snippets,
    reduce_markdown,
    reduce_sources,
)
from integration_research.validation import quote_exists
from tests.helpers import make_sources


def test_reduction_preserves_relevant_context_and_limit() -> None:
    text = (
        "irrelevant opening " * 50
        + "\n\n# Authentication\n\nBefore context.\n\nUse an OAuth token.\n\nAfter context."
        + "\n\nnoise " * 200
    )
    reduced = reduce_markdown(text, limit=300)
    assert len(reduced) <= 300
    assert "Authentication" in reduced
    assert "OAuth token" in reduced


def test_sources_receive_equal_share_of_app_limit() -> None:
    sources = list(make_sources().values())
    for source in sources:
        source.text = (source.text + "\n\nAPI authentication token webhook") * 1000
    reduced = reduce_sources(sources, per_page_limit=20_000, per_app_limit=60_000)
    assert set(reduced) == {"source_1", "source_2", "source_3", "source_4", "source_5"}
    assert all(len(text) <= 15_000 for text in reduced.values())
    assert sum(len(text) for text in reduced.values()) <= 60_000


def test_evidence_snippets_are_bounded_and_literal() -> None:
    sources = list(make_sources().values())
    reduced = {source.source_id: source.text for source in sources}
    snippets = build_evidence_snippets(sources, reduced)
    assert snippets
    assert all(len(snippet.text) <= 500 for snippet in snippets.values())
    source_map = {source.source_id: source for source in sources}
    assert all(
        quote_exists(snippet.text, source_map[snippet.source_id].text)
        for snippet in snippets.values()
    )
