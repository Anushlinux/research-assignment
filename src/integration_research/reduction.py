"""Bound fetched Markdown before it is sent to the extraction model."""

from __future__ import annotations

import re

from integration_research.models import FetchedSource

RELEVANT_TERMS: tuple[str, ...] = (
    "api",
    "authentication",
    "oauth",
    "token",
    "credentials",
    "authorization",
    "developer",
    "access",
    "pricing",
    "trial",
    "approval",
    "partner",
    "admin",
    "rest",
    "graphql",
    "webhook",
    "mcp",
)


def reduce_markdown(text: str, *, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text

    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    essential: set[int] = set()
    for index, block in enumerate(blocks):
        lowered = block.lower()
        is_heading = block.startswith("#")
        if is_heading or any(term in lowered for term in RELEVANT_TERMS):
            essential.add(index)

    selected_indices = set(essential)
    for index in sorted(essential):
        for neighbor in (index - 1, index + 1):
            if neighbor < 0 or neighbor >= len(blocks) or neighbor in selected_indices:
                continue
            tentative = "\n\n".join(blocks[item] for item in sorted({*selected_indices, neighbor}))
            if len(tentative) <= limit:
                selected_indices.add(neighbor)

    ordered = [blocks[index] for index in sorted(selected_indices)]
    selected = "\n\n".join(ordered)
    if len(selected) < limit:
        included = set(selected_indices)
        for index, block in enumerate(blocks):
            if index in included:
                continue
            candidate = f"{selected}\n\n{block}" if selected else block
            if len(candidate) > limit:
                break
            selected = candidate
    return selected[:limit]


def reduce_sources(
    sources: list[FetchedSource], *, per_page_limit: int, per_app_limit: int
) -> dict[str, str]:
    if not sources:
        return {}
    fair_limit = max(1, per_app_limit // len(sources))
    effective_page_limit = min(per_page_limit, fair_limit)
    reduced = {
        source.source_id: reduce_markdown(source.text, limit=effective_page_limit)
        for source in sources
    }
    total = sum(len(text) for text in reduced.values())
    if total > per_app_limit:
        raise AssertionError("source reduction exceeded the per-app limit")
    return reduced


def build_source_package(sources: list[FetchedSource], reduced: dict[str, str]) -> str:
    sections: list[str] = []
    for source in sources:
        sections.append(
            "\n".join(
                (
                    f"SOURCE {source.source_id}",
                    f"URL: {source.url}",
                    f"TITLE: {source.title}",
                    "",
                    reduced[source.source_id],
                )
            )
        )
    return "\n\n---\n\n".join(sections)
