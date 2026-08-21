# Composio Integration Research

An evidence-backed research agent that checks whether 100 apps can be used as callable integrations.

- **Live case study:** https://anushlinux.github.io/research-assignment/
- **Final page:** [`docs/index.html`](docs/index.html)
- **App catalog:** [`data/apps.csv`](data/apps.csv)

## What the agent does

For each app, the agent:

1. Searches for official authentication, credential-access, pricing, approval, and API documentation through Composio.
2. Fetches and stores the exact source text.
3. Uses OpenAI to extract structured claims from those sources.
4. Checks every material claim against stored evidence.
5. Marks the result `verified`, `needs_human_review`, or failed. Missing evidence stays `unknown`.

The latest run attempted all 100 apps. It produced 94 accepted records: 21 verified and 73 requiring human review. Six apps still failed after retries.

## Quick setup

Requirements: Python 3.12 and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --frozen
cp .env.example .env
```

Add these credentials to the ignored `.env` file:

```text
OPENAI_API_KEY=...
COMPOSIO_API_KEY=...
```

Never commit `.env` or generated run artifacts.

## Run all 100 apps with one command

```bash
uv run --frozen research run --all --run-id full-100
```

`--all` reads every app from `data/apps.csv`. Use a new `--run-id` when starting another immutable run.

The summary is written to:

```text
runs/full-100/run-summary.json
```

Each app keeps its sources, evidence snippets, drafts, validation results, corrections, metrics, and final record under `runs/full-100/apps/`.

## Run one app

```bash
uv run --frozen research run --app-id 61 --run-id github-check
```

The output appears under `runs/github-check/apps/061-github/`.

## Review the case study locally

```bash
uv run --frozen python scripts/build_case_study.py
python3 -m http.server 8000 --directory docs
```

Then open http://localhost:8000.

## Verify the project

```bash
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy src tests
uv run --frozen pytest
```

## Important boundaries

- Composio performs search and page retrieval.
- OpenAI interprets fetched sources; it is not used as the evidence search provider.
- Deterministic code decides which claims enter the final output.
- Paid, enterprise, administrator, sales, or partner access is a valid finding when supported by evidence.
- An app failure remains visible instead of being silently removed.
- Raw runs are ignored because they may contain provider responses or sensitive local state.

## Project map

- `src/integration_research/` — research pipeline
- `prompts/` — extraction and audit prompts
- `scripts/build_case_study.py` — HTML generator
- `verification/manual_sample.json` — 12-app claim-to-evidence sample
- `docs/composio-tool-schemas/` — inspected Composio tool schemas
- `docs/COMPOSIO_TAKEHOME_CONTEXT.md` — complete assignment context
- `AGENTS.md` — repository rules for coding agents
