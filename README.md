# Composio Integration Research

This repository is the foundation for an evidence-backed research pipeline that will evaluate 100 applications as potential agent-callable integrations.

## Current status

Only the repository scaffold is implemented. It includes the authoritative assignment context, canonical input data, locked Python dependencies, project guidance, tests, and continuous integration checks.

The research pipeline, command-line interface, Composio session, tool wrappers, prompts, pilot run, results, and HTML case study do not exist yet.

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

## Repository contracts

- `docs/COMPOSIO_TAKEHOME_CONTEXT.md` is the authoritative project brief.
- `data/apps.csv` is the canonical 100-app input.
- `src/integration_research/` is the Python package.
- `prompts/` will contain versioned model prompts once extraction work begins.
- `docs/composio-tool-schemas/` will contain schemas observed from the authenticated Composio CLI.
- `runs/` is reserved for generated run artifacts and is ignored except for its placeholder.
- `.state/` will contain reusable local session state and is fully ignored.

## Deferred next milestone

The next milestone is live-tool setup, not pipeline implementation:

1. Install and authenticate the Composio CLI.
2. Inspect and save the exact approved tool schemas.
3. Run one Composio search and one URL-content fetch smoke test.
4. Record the observed input and response shapes before writing wrappers.

No external service has been authenticated or called by this scaffold.

## Core project rules

- Search and page retrieval will happen through Composio.
- OpenAI will interpret fetched sources but will not act as the research search provider.
- Unsupported or conflicting claims remain `unknown`.
- Drafts and corrections remain separate and auditable.
- The five-app pilot must be inspected before any 100-app run.

See [`AGENTS.md`](AGENTS.md) for agent instructions and [`docs/COMPOSIO_TAKEHOME_CONTEXT.md`](docs/COMPOSIO_TAKEHOME_CONTEXT.md) for the full design.
