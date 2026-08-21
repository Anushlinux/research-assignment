# Composio Integration Research

This repository contains an evidence-backed research pipeline and a static case study covering 100 applications as potential agent-callable integrations.

## Case study

Open [`docs/index.html`](docs/index.html) directly, or serve it locally:

```bash
python3 -m http.server 8000 --directory docs
```

The page is self-contained. It presents the headline findings, category and authentication patterns,
the research workflow, the verification sample, all eight unresolved apps, and a searchable table of
all 100 attempts. Rebuild it from a local consolidated run with:

```bash
uv run --frozen python scripts/build_case_study.py
```

The completed bounded run attempted all 100 catalog apps: 92 produced final records and eight stayed
unresolved. Generated run artifacts remain ignored because they can contain raw provider responses.

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

## Run the research agent

Put `OPENAI_API_KEY` and `COMPOSIO_API_KEY` in the ignored `.env`, then run one catalog app:

```bash
uv run --frozen research run --app-id 61 --run-id single-app
```

The immutable record and its supporting artifacts are written under:

```text
runs/single-app/apps/061-github/
```

Run the five-app pilot sequentially, without concurrency:

```bash
uv run --frozen research run --ids 61,22,31,90,98 --run-id pilot-milestone-1-2
```

Every valid catalog ID is supported. Each immutable per-app attempt preserves the fetched
sources, exact evidence-snippet catalog, raw draft, literal validation, semantic-audit input and
result, admission diff, admitted draft, final validation, metrics, and final record. Fatal
structural or provenance failures do not create `final.json`; semantically unsupported claims
become explicit unknowns instead. A failed app is recorded and does not stop later IDs in the same
sequential run. The root `run-summary.json` records all successes and failures.

## Repository contracts

- `docs/COMPOSIO_TAKEHOME_CONTEXT.md` is the authoritative project brief.
- `data/apps.csv` is the canonical 100-app input.
- `src/integration_research/` is the Python package.
- `prompts/` contains the versioned, source-only extraction prompt.
- `docs/composio-tool-schemas/` contains schemas observed from the authenticated Composio CLI.
- `runs/` is reserved for generated run artifacts and is ignored except for its placeholder.
- `.state/` will contain reusable local session state and is fully ignored.

## Core project rules

- Search and page retrieval will happen through Composio.
- OpenAI will interpret fetched sources but will not act as the research search provider.
- A separate OpenAI call audits claim-to-evidence support without tools or browsing.
- Unsupported or conflicting claims remain `unknown`.
- Drafts and corrections remain separate and auditable.
- Inspect the five-app pilot before starting an all-app run.

See [`AGENTS.md`](AGENTS.md) for agent instructions and [`docs/COMPOSIO_TAKEHOME_CONTEXT.md`](docs/COMPOSIO_TAKEHOME_CONTEXT.md) for the full design.
