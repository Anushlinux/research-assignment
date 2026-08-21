from integration_research.reduction import reduce_markdown, reduce_sources
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


def test_four_sources_receive_equal_share_of_app_limit() -> None:
    sources = list(make_sources().values())
    for source in sources:
        source.text = (source.text + "\n\nAPI authentication token webhook") * 1000
    reduced = reduce_sources(sources, per_page_limit=20_000, per_app_limit=60_000)
    assert set(reduced) == {"source_1", "source_2", "source_3", "source_4"}
    assert all(len(text) <= 15_000 for text in reduced.values())
    assert sum(len(text) for text in reduced.values()) <= 60_000
