# AGENTS.md

## Required context

- Read `docs/COMPOSIO_TAKEHOME_CONTEXT.md` completely before changing project behavior.
- The repository currently contains the setup foundation only. Expand the scope only when the user explicitly asks.

## Communication

- Explain technical decisions in clear, plain English.
- Separate verified facts, assumptions, hypotheses, and recommendations.
- Never hide failures or replace missing evidence with confident wording.

## Engineering rules

- Use Python 3.12 and `uv`.
- Keep the implementation direct. Do not add speculative modules or framework layers.
- Use Composio Search and Browser Tool for future web retrieval. Use OpenAI only for inference over fetched sources; do not use OpenAI web search as evidence.
- Inspect installed Composio tool schemas before writing tool arguments. Never guess request or response shapes.
- Every future material claim that is not `unknown` must map to fetched evidence.
- Preserve raw, draft, validation, verification, diff, and final artifacts separately.
- Keep deterministic validation and buildability decisions outside model prompts.
- Never commit API keys, session headers, `.env`, `.state`, or generated research runs.
- Do not authenticate services, make live external calls, or run the pilot unless the current user request explicitly includes that work.
- Do not add LangChain, LangGraph, CrewAI, AutoGen, a database, Playwright, or a frontend during Phase 1.

## Verification before completion

- Run `uv sync --frozen`.
- Run `uv run --frozen ruff check .`.
- Run `uv run --frozen ruff format --check .`.
- Run `uv run --frozen mypy src tests`.
- Run `uv run --frozen pytest`.
- Confirm no secrets or generated run artifacts are tracked.
- Do not run all 100 apps until the five-app pilot for IDs `61,22,31,90,98` has been implemented and inspected.
