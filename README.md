# Composio Integration Research

This repository is the foundation for an evidence-backed research pipeline that will evaluate 100 applications as potential agent-callable integrations.

## Current status

Milestone 1.1 implements one synchronous, evidence-backed production path for GitHub (app ID 61).
It uses field-specific Composio searches, official-source selection, bounded page reduction,
deterministic exact-text evidence snippets, one tool-free OpenAI extraction call, and one
independent tool-free semantic evidence-audit call. The extractor selects stored snippet IDs rather
than generating quotations. Deterministic code admits only supported claims and computes
buildability.

MCP verification, Browser Tool fallback, concurrency, the five-app pilot, the remaining 99 apps, and the HTML case study are intentionally deferred.

## Requirements

- Python 3.12
- [`uv`](https://docs.astral.sh/uv/)

The project deliberately requires Python `>=3.12,<3.13`. This prevents the system Python or a newer experimental interpreter from being selected accidentally.

## Local setup

Install the exact locked dependencies:

```bash
uv sync --frozen
```

Create a local environment file only when live integration work begins:

```bash
cp .env.example .env
```

Add real credentials only to `.env`. That file is ignored by Git.

## Verification

Run the same checks used by continuous integration:

```bash
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy src tests
uv run --frozen pytest
```

## Run Milestone 1.1

Put `OPENAI_API_KEY` and `COMPOSIO_API_KEY` in the ignored `.env`, then run only GitHub:

```bash
uv run --frozen research run --app-id 61 --run-id github-milestone-1-1
```

The immutable record and its supporting artifacts are written under:

```text
runs/github-milestone-1-1/apps/061-github/
```

The command rejects every app ID other than 61. Each immutable attempt preserves the fetched
sources, exact evidence-snippet catalog, raw draft, literal validation, semantic-audit input and
result, admission diff, admitted draft, final validation, metrics, and final record. Fatal
structural or provenance failures do not create `final.json`; semantically unsupported claims
become explicit unknowns instead.

## Repository contracts

- `docs/COMPOSIO_TAKEHOME_CONTEXT.md` is the authoritative project brief.
- `data/apps.csv` is the canonical 100-app input.
- `src/integration_research/` is the Python package.
- `prompts/` contains the versioned, source-only extraction prompt.
- `docs/composio-tool-schemas/` contains schemas observed from the authenticated Composio CLI.
- `runs/` is reserved for generated run artifacts and is ignored except for its placeholder.
- `.state/` will contain reusable local session state and is fully ignored.

## Deferred next milestone

After the GitHub record has been inspected, the next milestone is the five-app pilot for IDs
`61,22,31,90,98`. Do not run the other apps or add the verifier before that review.

## Core project rules

- Search and page retrieval will happen through Composio.
- OpenAI will interpret fetched sources but will not act as the research search provider.
- A separate OpenAI call audits claim-to-evidence support without tools or browsing.
- Unsupported or conflicting claims remain `unknown`.
- Drafts and corrections remain separate and auditable.
- The five-app pilot must be inspected before any 100-app run.

See [`AGENTS.md`](AGENTS.md) for agent instructions and [`docs/COMPOSIO_TAKEHOME_CONTEXT.md`](docs/COMPOSIO_TAKEHOME_CONTEXT.md) for the full design.
