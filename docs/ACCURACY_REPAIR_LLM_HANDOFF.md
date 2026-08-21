# Accuracy Repair Handoff for the 100-App Integration Research Agent

## Purpose of this document

This document is a technical handoff for an LLM that must improve the accuracy of this repository quickly and in one focused implementation pass.

The repository contains a working first-pass research pipeline, but the current 100-app output must **not** be treated as a trustworthy final dataset. The pipeline is good at preserving evidence and refusing unsupported claims. It is not yet good at recovering when its first searches miss the correct developer documentation. It also labels structurally valid, incomplete records too positively.

The objective is not to redesign the whole project. The objective is to make the smallest high-leverage changes that:

1. Retrieve the right official developer evidence more reliably.
2. Separate product login from developer-interface authentication.
3. Prevent critical unknowns from being exported as final verified conclusions.
4. Run an actual evidence-gathering verification pass for difficult records.
5. Produce a small, measurable, defensible accuracy improvement before rerunning all 100 apps.

This document explains:

- What the assignment is asking for.
- What the current agent actually does.
- Which parts are deterministic and which parts use a model.
- How evidence becomes a final row.
- Why Attio and Podio exposed serious errors.
- Why the current output has so many unknown values.
- What is implemented versus only planned.
- The smallest repair plan likely to improve accuracy under a tight deadline.
- Exact acceptance tests and stop conditions.

## Read this first

Before changing behavior, read these files completely:

1. `AGENTS.md`
2. `docs/COMPOSIO_TAKEHOME_CONTEXT.md`
3. This document

The project rules are strict:

- Use Python 3.12 and `uv`.
- Use Composio Search and Browser Tool for external research.
- Use OpenAI only to interpret fetched sources, not as an independent web-search provider.
- Inspect the actual Composio schemas before changing tool arguments.
- Preserve raw, draft, audit, validation, diff, and final artifacts separately.
- Do not commit API keys, session headers, `.env`, `.state`, or generated research runs.
- Do not add LangChain, LangGraph, CrewAI, AutoGen, a database, Playwright, or a frontend.
- Do not run all 100 apps until the repaired pilot has been inspected.
- Do not make live external calls unless the user explicitly authorizes a live run.

## Executive diagnosis

### Verified current outcome

The consolidated output contains 100 rows:

- 84 were produced on their first run.
- 8 were recovered by retries.
- 8 still failed after retries.
- 28 have `buildability = yes`.
- 21 have `buildability = conditional`.
- 51 have `buildability = unknown`.

Of the 51 unknown buildability rows, 8 are failed rows and 43 are records that the export otherwise treats as successful.

All 92 records that produced a `final.json` still contain unresolved questions. Across the consolidated output, there are 595 unresolved questions.

Important field-level gaps in the current 100 rows include:

- 55 rows with unknown credential access.
- 92 rows with unknown production gating.
- 36 rows with unknown API breadth.
- 38 rows with unknown MCP status.
- 17 rows with unknown authentication.

These counts prove that the current output is a first-pass research dataset, not a finished accuracy-verified deliverable.

### Core failure in one sentence

The pipeline can remove claims that its selected evidence does not support, but it cannot obtain better evidence after weak source selection, so it converts retrieval misses into `unknown` values and then exports those incomplete records as if they were final.

### What is still valuable

The repository is not useless. It already has valuable foundations:

- Strict Pydantic schemas.
- Catalog-anchored official-domain trust.
- Immutable per-app run artifacts.
- Exact source and snippet provenance.
- Literal evidence validation.
- A second model call that audits claim-to-evidence support.
- Deterministic buildability rules.
- Failure isolation between apps.
- Consolidated output and a static case-study generator.

The repair should preserve these strengths.

## What the assignment requires

For each of 100 apps, the system must research:

- What the product does.
- Which authentication methods its developer interfaces use.
- How a developer obtains credentials.
- Whether access is self-serve, admin-controlled, vendor-reviewed, partner-only, or sales-gated.
- Whether a public callable interface exists.
- Which API style or local interface it uses.
- How broad the callable surface is.
- Whether read and write operations are possible.
- Whether webhooks, an official SDK, a CLI, or an MCP server exist.
- Whether a toolkit can realistically be built now.
- What blocks the integration if it cannot be built now.
- Which official pages support each material conclusion.

The deeper evaluation is not just whether 100 JSON rows exist. The reviewer is testing whether the candidate designed a reliable research operation with:

- Correct source discovery.
- Product identity resolution.
- Claim-level evidence.
- Honest uncertainty.
- Deterministic validation.
- Recovery from weak or inaccessible documentation.
- Measured verification rather than an unsupported accuracy claim.

## Repository map

### Authoritative inputs and instructions

- `AGENTS.md`: short repository-specific operating rules.
- `docs/COMPOSIO_TAKEHOME_CONTEXT.md`: complete project brief and intended architecture.
- `data/apps.csv`: canonical list of 100 apps.
- `docs/composio-tool-schemas/`: schemas observed from the installed Composio tools.

### Runtime code

- `src/integration_research/models.py`: strict enums and Pydantic contracts.
- `src/integration_research/settings.py`: environment-backed limits and model configuration.
- `src/integration_research/composio_session.py`: Composio session and tool execution wrapper.
- `src/integration_research/source_selection.py`: search planning, trusted-domain policy, candidate scoring, and source selection.
- `src/integration_research/reduction.py`: page reduction and stable evidence snippets.
- `src/integration_research/extraction.py`: first OpenAI structured extraction call.
- `src/integration_research/validation.py`: deterministic structural, provenance, and consistency validation.
- `src/integration_research/audit.py`: second OpenAI call that checks whether selected quotations support extracted claims.
- `src/integration_research/verdict.py`: deterministic buildability and integration-path calculation.
- `src/integration_research/storage.py`: immutable run artifact writing.
- `src/integration_research/pipeline.py`: end-to-end orchestration for one app and sequential batches.
- `src/integration_research/cli.py`: `research run` command.

### Prompts

- `prompts/extract.md`: source-only structured extraction instructions.
- `prompts/audit.md`: source-only claim-to-evidence auditing instructions.

### Current generated outputs

- `runs/full-100-20260822-consolidated/results.json`: consolidated 100-row result.
- `runs/full-100-20260822-consolidated/results.csv`: flattened output.
- `runs/full-100-20260822-consolidated/summary.json`: headline counts.
- `verification/manual_sample.json`: a 12-app, 60-claim evidence-agreement sample.
- `scripts/build_case_study.py`: renders the consolidated output into `docs/index.html`.

Generated runs are normally ignored by Git. Existing local runs are important diagnostic evidence but should not be committed automatically.

## Actual current agent behavior

This section describes what the code does now, not what the original design intended.

### 1. Load one catalog app

`pipeline.load_app_catalog()` reads `data/apps.csv` and constructs an `AppInput` containing:

- `app_id`
- `app_name`
- `website_hint`
- `category`
- `notes`

The website hint is identity context and the starting trust boundary. It is not automatically treated as evidence for a material claim.

### 2. Derive a trusted-source policy

`source_selection.derive_trusted_source_policy()` converts the catalog hint into:

- Trusted seed URLs.
- Trusted root hosts.
- Required repository path prefixes for shared code-forge hosts such as GitHub.

For a normal product such as `attio.com`, the trust policy allows the root host and its subdomains, including `docs.attio.com`.

For a GitHub catalog hint, host trust alone is not enough because unrelated repositories share `github.com`. The owner and repository path become part of the trust boundary.

This is a good precision-first rule and should be preserved.

### 3. Build five fixed searches

The pipeline creates exactly one search plan for each role:

1. `authentication`
2. `credential_access`
3. `api_surface`
4. `commercial_or_production_gate`
5. `mcp`

Each search is built from:

- A `site:` restriction derived from the catalog host.
- Quoted app name.
- Category.
- Website hint and notes.
- Fixed role-specific terms.

Examples of role terms:

- Authentication: `developer API authentication OAuth token API key service account`
- Credential access: `developer credentials create key token signup self serve administrator access`
- API surface: `developer API REST GraphQL RPC CLI SDK webhooks endpoints`
- Commercial or production gate: `API pricing production approval app review partner admin contact sales`
- MCP: `MCP "Model Context Protocol" agent callable CLI server`

`RESEARCH_MAX_SEARCHES_PER_APP` defaults to 5, and the pipeline requires all five roles to fit within the limit.

### 4. Execute Composio Search

For each role, the pipeline calls:

```text
COMPOSIO_SEARCH_WEB
```

with:

```json
{"query": "..."}
```

The raw response, latency, log ID, arguments, and any error are stored under:

```text
runs/<run_id>/apps/<app>/searches/
```

The code uses citation URLs returned by search. The generated search answer is not directly admitted as claim evidence. This is a correct evidence boundary because search summaries can synthesize or overstate source content.

### 5. Rank official candidate URLs

Candidate URLs are accepted only when the catalog-derived trust policy recognizes their host and path.

The ranker gives points for:

- Official developer documentation.
- Official repository.
- Official help or pricing pages.
- Matching the requested research role.
- Developer-oriented URL paths such as `/docs`, `/developer`, `/api`, or `/rest`.
- Exact or descendant relationship to the catalog hint.

It penalizes:

- Blogs.
- Communities and forums.
- Unrelated paths on a shared trusted host.

The catalog seed itself is also added as a fallback candidate with a penalty.

### 6. Select at most one source per role

`select_sources()` sorts candidates independently for each role and selects only the top candidate for that role.

The global maximum defaults to five. Therefore the normal result is:

- One authentication page.
- One credential-access page.
- One API-surface page.
- One pricing or production-gate page.
- One MCP page.

If the same URL wins multiple roles, it is fetched once and tagged with multiple roles.

This one-page-per-role design is one of the largest accuracy bottlenecks. A single weak ranking decision can leave a whole critical field unresolved.

### 7. Fetch selected pages

The pipeline calls:

```text
COMPOSIO_SEARCH_FETCH_URL_CONTENT
```

with one URL at a time and requests text output.

A fetched source is considered successful only when:

- The tool returns no error.
- Non-empty text is returned.
- The returned URL is still trusted.
- The returned URL can be classified into an official source tier.

Each source stores:

- URL and title.
- Source role or roles.
- Source tier.
- Full fetched text.
- Retrieval time.
- Content hash.
- Tool log ID.
- Raw tool response.
- Latency.

The current normal path does not use Browser Tool when search results are irrelevant or when a more specific documentation page is needed.

### 8. Reduce sources and create stable snippets

The pipeline reduces page content according to:

- `RESEARCH_MAX_CHARS_PER_PAGE`, default 20,000.
- `RESEARCH_MAX_CHARS_PER_APP`, default 60,000.

It then splits the retained source text into exact evidence snippets. Each snippet has a deterministic-looking identifier such as:

```text
source_2_snippet_010
```

Snippets are limited to 500 characters and retain their source relationship.

The extraction model must cite source and snippet IDs instead of writing its own URLs or quotations.

### 9. Run source-only structured extraction

`OpenAIExtractionClient` calls the configured extraction model, currently defaulting to `gpt-5.6-luna`.

The model receives:

- The app identity.
- The complete extraction prompt.
- Only the selected fetched source package.
- Stable source and snippet IDs.

The model cannot browse. It must return one strict `AppResearchDraft`.

It extracts:

- Description.
- Authentication methods.
- Credential access.
- Commercial requirement.
- Production gate.
- API availability.
- API styles.
- Webhooks.
- Official SDK.
- CLI.
- API breadth.
- Read and write capability.
- API surface summary.
- MCP status.
- Blocker.
- Unresolved questions.

The model does **not** decide buildability.

### 10. Normalize unknown bookkeeping

`normalize_unknown_questions()` ensures every unknown material field has a matching unresolved question.

This normalization does not research the missing fact and does not change unknown to known. It only repairs bookkeeping.

### 11. Run deterministic literal validation

`validate_draft()` checks facts that code can prove without semantic interpretation:

- App ID, name, and category match the catalog.
- Known claims are not empty.
- Every known material claim has evidence.
- Referenced source IDs exist.
- Referenced snippet IDs exist.
- A snippet belongs to the cited source.
- The exact normalized quotation occurs in the fetched source.
- Unknown values have unresolved questions.
- API combinations are structurally consistent.
- Duplicate auth methods or API styles are rejected by the model schema.

If literal validation fails, the app fails and no final record is written.

Critical limitation: literal validation proves provenance and structural consistency. It does not prove that the selected pages are comprehensive or that the model chose the best taxonomy value.

### 12. Run a tool-free semantic evidence audit

`OpenAIAuditClient` calls the configured stronger model, currently defaulting to `gpt-5.6-terra`.

The auditor receives:

- Each non-unknown normalized claim.
- A field definition.
- The exact supporting quotations.
- Nearby source context.
- Source title and roles.

It returns one of:

- `direct_support`
- `partial_support`
- `unsupported`

The auditor cannot browse and cannot request more sources.

This component is an evidence auditor, not a research verifier.

### 13. Apply semantic admission

`apply_semantic_audit()` changes the draft according to audit results:

- Directly supported claims remain.
- Partially supported or unsupported scalar claims become `unknown`.
- Unsupported API styles are removed.
- Unsupported authentication methods are removed or narrowed in one special OAuth-token case.
- An unresolved question is added for each removed claim.

The admission diff and admitted draft are stored separately.

This step increases precision by preferring unknown over unsupported claims. It also increases unknown counts when retrieval was weak.

### 14. Run final deterministic validation

The admitted draft goes through `validate_draft()` again.

If there are no structural, provenance, or consistency errors, `valid = true`, even when many critical fields remain unknown.

This is the source of the misleading `validated` concept in downstream export. The record is structurally and evidentially valid, but it may be deeply incomplete.

### 15. Compute buildability deterministically

`compute_buildability()` first decides whether a usable callable surface exists:

- Available API with at least one API style.
- Official MCP.
- Usable CLI.

It then applies access rules:

- Explicitly unavailable credentials produce `no`.
- Admin, vendor, partner, or sales-controlled access produces `conditional`.
- App review or another explicit approval gate produces `conditional`.
- An evidence-backed blocker produces `conditional`.
- Self-serve or no-auth access can produce `yes`.
- Unknown credential access produces `unknown` even when an API or official MCP exists.

The buildability code is cautious by design. Most excessive unknown verdicts are caused by missing credential-access evidence upstream, not by random model judgment in the verdict stage.

### 16. Write immutable artifacts

For a successful app, the pipeline writes artifacts such as:

```text
input.json
searches.json
searches/*.json
selected-sources.json
sources/source_*.json
evidence-snippets.json
extraction-input.json
draft.json
normalized-draft.json
literal-validation.json
semantic-audit-input.json
semantic-audit.json
admission-diff.json
admitted-draft.json
final-validation.json
final.json
metrics.json
report.json
```

For a failed app, it writes `failure.json` and preserves the earlier stage artifacts.

This artifact separation is strong and must be preserved during repair.

### 17. Sequence multiple apps

The CLI can execute one app or a comma-separated list sequentially.

One app failure does not stop later apps. A root run summary records successful and failed app IDs.

### 18. Identify verifier and browser candidates without processing them

At the end of a sequence, the pipeline builds:

- `requires_deeper_research`
- `mcp_verifier_candidates`
- `browser_tool_candidates`

Any record with unresolved questions becomes a deeper-research and MCP-verifier candidate.

However, the code only writes these lists into `pilot-summary.json`. There is no `verifier.py`, no correction loop, and no Browser Tool execution in the normal pipeline.

This is the largest gap between the intended architecture and current implementation.

## What each component is responsible for

### Deterministic code

Deterministic code currently owns:

- Catalog input validation.
- Trusted host and repository boundary.
- Search plan generation.
- Candidate URL ranking.
- Selection budget.
- Source fetch validation.
- Page reduction and snippet creation.
- Exact quotation existence checks.
- Schema consistency.
- Claim downgrade application.
- Buildability.
- Artifact persistence.
- Run summaries.

Deterministic code should continue to own final admission and buildability.

### Extraction model

The extraction model owns interpretation of the selected source package:

- Mapping documentation language into enums.
- Selecting relevant snippets.
- Summarizing API coverage.
- Returning unknown when selected sources are insufficient.

It must never use prior knowledge as evidence.

### Semantic audit model

The audit model owns a narrow question:

> Do these exact quotations support this normalized claim at this specificity?

It does not own source discovery, conflict resolution across newly fetched pages, or final buildability.

### Missing verifier

The intended verifier should own:

- Researching only disputed or missing critical fields.
- Running additional Composio searches.
- Fetching new official pages.
- Using Browser Tool only when search/fetch cannot access the needed content.
- Returning structured corrections with new evidence.
- Preserving a verification artifact and diff.

This component does not currently exist.

## Current schema and why it creates ambiguity

### Authentication enum

The current high-level authentication enum is:

```text
oauth2
api_key
basic
token
other
none
unknown
```

Each known authentication method also has free-text implementation details and evidence.

### Current flattening problem

`auth_methods` is stored once per app. It is not attached to a specific integration surface.

This can mix together:

- SaaS product login.
- REST API authentication.
- Private workspace integration authentication.
- Public OAuth application authentication.
- Hosted MCP authentication.
- Local CLI authentication.

This makes output hard to interpret. For example, Attio can have:

- Workspace API keys for private REST integrations.
- An authorization-code OAuth path for public apps.
- OAuth for hosted MCP.
- Google sign-in for customer login.

These are not interchangeable facts.

### Scrappy schema recommendation

Do not perform a full schema rewrite unless necessary. The fastest safe improvement is to add an evidence-backed `auth_scope` or `integration_surface` to each authentication method.

For example:

```json
{
  "method": "oauth2",
  "integration_surface": "public_rest_app",
  "details": "Authorization-code flow using client ID, client secret, and bearer access token.",
  "evidence": []
}
```

Possible bounded surface values:

```text
rest_api
graphql_api
public_app
private_workspace_integration
hosted_mcp
local_cli
other
```

If changing the schema would consume too much time, keep the existing schema but require every auth `details` string to begin with a clear surface label such as `REST API:` or `Hosted MCP:`. Also prohibit product-login evidence unless it directly establishes developer credential access.

## Product login versus developer authentication

This distinction must be explicit in the repaired prompt and tests.

### Product login

Examples:

- “Sign in with Google.”
- Email and password login.
- SAML single sign-on for employees.

This explains how a human signs into the product. It does not prove how a third-party integration authenticates to a REST API or MCP server.

### Developer-interface authentication

Examples:

- OAuth 2.0 authorization-code flow.
- API key generated in workspace settings.
- Basic authentication using an API credential.
- Personal or workspace access token.
- Service account.
- Signed request.
- No authentication for a local CLI operating only on local files.

Only developer-interface authentication belongs in the integration-auth output.

### Practical rule

Never classify API authentication from a normal login page alone.

An OAuth-looking login button may prove that the product itself is an OAuth client of Google. It does not prove that the product is an OAuth authorization server for third-party developers.

## Attio failure analysis

### What the pipeline fetched

The Attio run fetched five strong official pages, including:

- `https://docs.attio.com/docs/oauth/token`
- `https://attio.com/help/reference/apps/generating-an-api-key`
- `https://docs.attio.com/rest-api/overview`
- `https://attio.com/pricing`
- `https://docs.attio.com/mcp/overview`

The stored official documentation includes:

- An app client ID.
- An app client secret.
- `authorization_code` as the grant type.
- A code received from `/authorize`.
- A bearer access token used for the REST API.
- Workspace API keys/access tokens created by administrators.
- Explicit OAuth wording for Attio MCP.

### What the model returned

The draft classified Attio authentication as:

```text
other; api_key
```

The `other` details described the authorization-code flow accurately but said the excerpts did not explicitly identify it as OAuth 2.0.

### Why this is incorrect

The extraction prompt allows OAuth2 when there is either:

1. Text explicitly establishing OAuth 2.0, or
2. Dedicated OAuth application documentation.

The source is dedicated OAuth token documentation and describes the standard authorization-code grant. Therefore `other` conflicts with the intended classification rule.

The semantic auditor marked the `other` claim directly supported because the evidence supported the details of the flow. It failed to challenge whether `other` was the correct taxonomy label.

This shows a semantic-audit weakness:

- It checks whether the evidence supports the prose claim.
- It does not always compare the chosen enum against better matching enum definitions.

### Expected repaired result

At minimum, the stored evidence should support:

```text
oauth2; api_key
```

with clear surface-specific details:

- OAuth2 for the public app or authorization-code REST integration path.
- API key or workspace access token for admin-created private workspace access.
- OAuth for hosted MCP, if MCP authentication is included in the same auth summary.

Do not use Attio's Google login button as the evidence for this conclusion. Use developer documentation.

### Required regression test

Given an official page under a dedicated OAuth documentation path containing client ID, client secret, `authorization_code`, `/authorize`, access token, and bearer token, the extractor/auditor contract must not admit `other` when `oauth2` is the correct supported enum.

## Podio failure analysis

### What search returned

The five Podio searches mostly returned:

- Marketing pages.
- Extension listings.
- Workflow automation help pages.
- Old company resources.
- The Podio homepage.

They did not return or select a useful official developer authentication or API-reference page.

### What the pipeline fetched

The source selector ultimately fetched only:

```text
https://podio.com/
```

The homepage contained broad marketing statements such as “API-first flexibility” and “robust APIs,” but no endpoint, authentication, credential, protocol, or access documentation.

### What happened next

The extraction model initially returned `api_availability = yes` from the marketing claims.

The semantic auditor correctly narrowed this to unknown because “robust APIs” does not establish a supported callable developer API.

The final record therefore had unknown values for almost every integration field.

The metrics showed:

```text
search_calls = 5
fetch_calls = 1
browser_calls = 0
```

### Why Podio was still exported

The final record passed structural and provenance validation because:

- Unknown is a legal schema value.
- Unknown claims had unresolved questions.
- The remaining description claim had literal evidence.
- No internal contradictions remained.

The pipeline then wrote `final.json` and downstream consolidation called the row validated.

### Required repaired behavior

If only a generic homepage is available for authentication, API style, or credential access:

1. The record must not be considered final.
2. The pipeline must try focused follow-up discovery.
3. It should inspect official developer subdomains or linked developer pages.
4. It should try documentation indexes or sitemap-like entry points where available.
5. If direct fetch still fails, it should use bounded Browser Tool navigation.
6. If the critical facts remain unresolved, the row should become `needs_human_review`, not `validated`.

Do not hard-code unverified Podio auth values merely to remove unknowns. Fetch and store official evidence first.

## Why buildability is especially confusing

Buildability is intended to answer:

> Can an agent-callable integration realistically be built today, and what blocks it?

The current logic is deterministic, but a single app-level verdict hides the path that caused it.

### Current decision shape

```text
Is there an available API with a known style, official MCP, or usable CLI?
    no -> no only if all paths are explicitly absent; otherwise unknown
    yes -> continue

Are credentials explicitly unavailable?
    yes -> no

Does access require admin, vendor, partner, sales, or production approval?
    yes -> conditional

Is there another evidence-backed blocker?
    yes -> conditional

Is credential access self-serve or not required?
    yes -> yes
    no or unknown -> unknown
```

### Why many rows become unknown

The search strategy frequently finds API overview pages but fails to find credential-creation pages. Therefore:

- Callable API is known.
- REST or another style is known.
- Authentication may be known.
- Credential access remains unknown.
- Final buildability becomes unknown.

This is cautious and preferable to inventing self-serve access, but it means credential-access retrieval is a critical path for the whole assignment.

### Recommended output improvement

Expose the reasoning path, not only the enum. For example:

```json
{
  "buildability": "conditional",
  "path": "rest_api",
  "surface_available": "yes",
  "authentication": ["oauth2"],
  "credential_access": "admin_required",
  "production_gate": "unknown",
  "reason": "A callable REST API exists, but a workspace administrator must create credentials."
}
```

This can be added as a derived explanation without replacing the existing top-level enum.

## Why the existing verification number is insufficient

`verification/manual_sample.json` describes a 12-app sample with 60 checked claims:

- 52 of 60 first-pass claims were supported by stored excerpts.
- 60 of 60 final sampled claims were supported after unsupported claims were removed or corrected.

This is useful, but it measures **evidence agreement**, not complete factual accuracy.

It answers:

> Does the stored excerpt support the sampled final claim?

It does not fully answer:

- Did the search find the correct official documentation?
- Did the system omit a supported auth method?
- Did it choose unknown because retrieval failed?
- Is a negative or not-found conclusion complete?
- Is the buildability verdict correct for the best available integration path?
- Did the app's documentation change?

The case-study generator displays the sample as a strong verification improvement. The repaired system must label this metric accurately and add field-level completeness or manual-gold comparison before claiming broad accuracy.

## Primary root causes

### Root cause 1: Retrieval is fixed rather than adaptive

The pipeline always runs five predefined searches. It does not observe which fields remain unresolved and create targeted follow-up queries.

### Root cause 2: One selected page per role is too brittle

Authentication and access often require multiple official pages:

- Authentication overview.
- OAuth guide.
- API key creation help article.
- Developer portal signup page.
- App review documentation.

Selecting only one page loses this multiplicity.

### Root cause 3: Page ranking relies heavily on URL and title terms

A high-ranked page can match “token” or “API” in its path but still omit the exact fact needed for the field.

There is no post-fetch page-quality gate asking whether the page contains expected evidence signals.

### Root cause 4: The audit cannot gather missing evidence

The stronger model receives only the original quotations. It cannot correct a retrieval miss.

### Root cause 5: Planned verification is not implemented

The code identifies every unresolved record as a verifier candidate, but no verifier consumes that queue.

### Root cause 6: Structural validity is presented as research completion

Unknown-rich records can pass validation and be exported as successful.

### Root cause 7: Authentication is not scoped to an interface

Product login, REST API, public app, private token, and MCP auth can be conflated.

### Root cause 8: Taxonomy audits are weaker than evidence audits

The semantic auditor may confirm that prose details are supported without detecting that a different enum better represents those details.

### Root cause 9: The pilot did not block the full run

The intended design said the five-app pilot must be inspected before all 100 apps. The actual full run proceeded while the architecture still lacked the real verifier and browser fallback.

## Accuracy repair strategy

The implementation should optimize for high-leverage corrections under a short deadline.

Do not start by rerunning all 100 apps. Repair the control flow first.

### Priority 0: Stop calling incomplete records final

This is the fastest way to prevent misleading output.

Add explicit record stages or statuses:

```text
first_pass_structurally_valid
needs_verification
verified
needs_human_review
failed
```

A record with critical unknown fields must not be `verified`.

Recommended critical fields:

- `auth_methods`
- `credential_access`
- `api_availability`
- At least one usable interface: API style, official/community MCP, or CLI
- `api_breadth` when API availability is yes or limited
- Buildability explanation and path

Production gate can remain unknown only if the output makes that uncertainty visible and the buildability logic does not silently claim unconditional production readiness.

Suggested deterministic completeness levels:

```text
complete:
  all critical fields known and evidence-backed

usable_with_explicit_uncertainty:
  callable path and credential path known, but non-critical fields remain unknown

needs_verification:
  one or more critical fields unknown, or source quality is insufficient

failed:
  no structurally valid record
```

Rename downstream `validated` to `first_pass_structurally_valid` unless it passes the completeness and verifier gates.

### Priority 1: Make retrieval adaptive

Keep the initial five searches, then perform targeted follow-up only for missing critical fields.

#### Initial source budget

Instead of one page per role, select up to two strong distinct pages for:

- Authentication.
- Credential access.
- API surface.

One page may remain sufficient for:

- Pricing or production gate.
- MCP.

Use a total normal-path budget around 7 to 8 pages per app, not an unbounded crawl.

#### Post-fetch page-quality signals

After fetching, deterministically inspect text for role-specific signals.

Authentication signals:

```text
oauth
authorization code
client id
client secret
api key
access token
authentication
authorization header
basic auth
```

Credential-access signals:

```text
create key
generate token
developer portal
workspace settings
admin
register app
request access
contact sales
partner
```

API-surface signals:

```text
endpoint
request
response
GET
POST
PUT
PATCH
DELETE
REST
GraphQL
RPC
resource names
```

A generic homepage with only phrases such as “robust APIs” should score as insufficient for a critical developer role.

#### Follow-up query generation

When a critical field remains unknown, create a deterministic query template using the specific missing field.

Examples:

```text
site:<trusted-host> "<app>" developer authentication oauth api key
site:<trusted-host> "<app>" create API credentials admin developer portal
site:<trusted-host> "<app>" REST API endpoint reference
site:<trusted-host> "<app>" app review production approval
```

Also search likely official subdomains derived from trusted citations and official links:

```text
developer.<root>
developers.<root>
docs.<root>
api.<root>
support.<root>
help.<root>
```

Do not blindly trust a guessed subdomain. It still must resolve through Composio and pass the existing root-host trust policy.

#### Documentation index discovery

When a fetched developer page advertises one of these, use it as a bounded discovery source:

- `llms.txt`
- Documentation index.
- API reference index.
- Sitemap.
- “Authentication,” “Getting started,” or “Developer settings” links.

Do not parse the whole site. Select only links relevant to unresolved critical fields.

### Priority 2: Implement an actual verifier

Create a direct, bounded verifier rather than a general autonomous agent.

Suggested file:

```text
src/integration_research/verifier.py
```

Suggested input:

```json
{
  "app": {},
  "first_pass_record": {},
  "disputed_fields": [],
  "existing_sources": [],
  "unresolved_questions": [],
  "remaining_tool_budget": {}
}
```

Suggested responsibilities:

1. Build field-specific Composio Search queries.
2. Rank results through the same trusted-source policy.
3. Fetch new official pages.
4. Use Browser Tool only when fetch cannot reach meaningful public content.
5. Build snippets for new sources.
6. Ask the stronger model for a structured correction limited to disputed fields.
7. Re-run literal validation and semantic audit.
8. Apply corrections through deterministic admission.
9. Write verification and diff artifacts.

Suggested output artifacts:

```text
verification-request.json
verification-searches.json
verification-sources/source_*.json
verification-snippets.json
verification-draft.json
verification-audit.json
verification-diff.json
verified-final.json
```

Do not overwrite the original first-pass artifacts.

#### Bounded budgets

Recommended maximum per app:

- Initial searches: 5.
- Initial fetches: 7 or 8.
- Verification searches: 3.
- Verification fetches: 3.
- Browser tasks: 1.
- Verification model calls: 1 extraction/correction plus 1 audit.

The verifier should stop once all critical disputed fields are resolved or the budget is exhausted.

If the budget is exhausted, produce `needs_human_review` with exact missing fields and attempted URLs.

### Priority 3: Strengthen authentication classification

Update `prompts/extract.md` and `prompts/audit.md` with explicit rules:

1. Exclude normal product login unless it directly controls developer access.
2. Attach every auth claim to a developer surface in details or schema.
3. Treat dedicated OAuth application documentation plus authorization-code grant semantics as OAuth2 when the project taxonomy allows that level of inference.
4. Do not create both `token` and `oauth2` merely because OAuth2 uses bearer tokens.
5. Do not call client ID/client secret alone an API key without documentation.
6. Do not call a bearer transport scheme a distinct auth method when the underlying method is OAuth2 or API key.

Add a deterministic taxonomy check before semantic audit:

- If `other` details contain strong OAuth2 authorization-code signals and evidence comes from a dedicated official OAuth page, flag the claim for correction or verification.
- If `token` details explicitly describe API-key creation, flag possible misclassification.
- If multiple auth methods have identical evidence and describe the same credential path, flag duplication.

The check should flag or route to verification. Avoid silently rewriting ambiguous evidence.

### Priority 4: Make source completeness part of validation

Add a separate `CompletenessReport`. Do not overload literal `ValidationReport`.

Suggested fields:

```json
{
  "critical_unknown_fields": [],
  "weak_source_roles": [],
  "generic_homepage_only_roles": [],
  "conflicting_fields": [],
  "requires_verification": true,
  "eligible_for_final_export": false
}
```

Suggested weak-source rules:

- Authentication supported only by official marketing homepage.
- API availability supported only by broad marketing language.
- Credential access has no settings, portal, admin, registration, or request-access evidence.
- API breadth known from one generic overview without resource or operation evidence.
- `mcp_status = not_found` without a bounded search log.
- `production_gate = none` without explicit no-review/no-approval evidence.

### Priority 5: Improve buildability explanations without loosening evidence

Keep buildability deterministic.

Do not make unknowns disappear by assuming credentials are self-serve.

Instead:

1. Derive candidate integration paths separately.
2. Evaluate access for each path.
3. Choose the best evidence-backed path.
4. Store the exact blocking field.

Example:

```text
Path: official MCP
Surface: established
Auth: OAuth2
Credential access: self-serve
Production approval: unknown
Verdict: yes for workspace use; marketplace distribution not evaluated
```

This avoids making a general marketplace-review unknown block a clearly usable private integration path.

Be careful: path-specific buildability must not silently convert an unknown production requirement into a claim of unrestricted production distribution.

### Priority 6: Run a repaired pilot before all 100

Use a seven-app accuracy pilot:

```text
4   Attio
6   Podio
22  Twilio
31  Google Ads
61  GitHub
90  PitchBook
98  Mermaid CLI
```

Why these apps:

- Attio: multiple auth paths and current taxonomy error.
- Podio: retrieval failure and homepage-only evidence.
- Twilio: multiple credential patterns.
- Google Ads: developer token, OAuth, customer account, and production review distinctions.
- GitHub: broad self-serve platform and OAuth/token taxonomy sensitivity.
- PitchBook: enterprise or gated access.
- Mermaid CLI: buildable local path without SaaS API credentials.

Do not run all 100 until these seven records have been manually inspected field by field.

## Scrappy implementation plan

If time is extremely limited, implement in this order.

### Pass A: Prevent misleading output

Estimated scope: small.

1. Add `CompletenessReport`.
2. Mark critical unknown records `needs_verification`.
3. Rename first-pass `validated` status in consolidation and presentation.
4. Exclude `needs_verification` rows from “buildable now” headline claims.
5. Make the case study disclose the exact number of incomplete records.

This does not improve retrieval, but it immediately improves honesty and prevents incorrect conclusions.

### Pass B: Add adaptive second search and multi-page selection

Estimated scope: medium.

1. Select up to two pages for authentication, credential access, and API surface.
2. Add post-fetch role-quality checks.
3. If a critical role is weak, run one focused follow-up query.
4. Fetch the strongest new official page.
5. Re-run extraction with the expanded source package.

This is likely the best accuracy improvement per unit of implementation time.

### Pass C: Add bounded verification loop

Estimated scope: medium to large.

1. Consume `mcp_verifier_candidates` instead of only writing them.
2. Verify only critical unknown or disputed fields.
3. Preserve original and corrected artifacts.
4. Add one Browser Tool fallback for inaccessible docs.

If there is not enough time for a full MCP-agent implementation, implement a deterministic direct Composio follow-up verifier first. The assignment values evidence and reliability more than agent-framework complexity.

### Pass D: Run and inspect seven apps

Do not parallelize the first repaired acceptance run. The goal is inspectability, not throughput.

After those seven pass, run the remaining apps in small batches and stop if the critical-unknown rate remains high.

## Exact code-change map

### `src/integration_research/models.py`

Recommended additions:

- Optional `integration_surface` on auth methods, or require a surface label in details.
- `RecordStatus` enum.
- `CompletenessReport` model.
- Verification request/correction models.
- Path-specific buildability explanation model if time permits.

Preserve strict `extra="forbid"` behavior.

### `src/integration_research/source_selection.py`

Recommended changes:

- Permit more than one distinct source for critical roles.
- Add content-quality assessment after fetch, probably in a separate small helper if clearer.
- Add targeted follow-up search plans for missing fields.
- Keep catalog-derived host trust.
- Do not accept arbitrary model-proposed domains as official.

### `src/integration_research/pipeline.py`

Recommended changes:

- Perform first-pass completeness assessment.
- Trigger bounded targeted research for critical gaps.
- Invoke the real verifier when needed.
- Write verification artifacts and corrections separately.
- Only write/export a verified final when eligibility rules pass.
- Continue preserving per-app failures.

### `src/integration_research/audit.py`

Recommended changes:

- Make enum alternatives explicit in audit input.
- Ask whether the chosen enum is the best supported taxonomy value, not only whether the prose is supported.
- Add deterministic pre-audit taxonomy warnings.
- Keep the audit tool-free. New browsing belongs in the verifier.

### `src/integration_research/verdict.py`

Recommended changes:

- Derive path-specific explanations.
- Preserve evidence-first caution.
- Do not make unknown credential access self-serve by assumption.

### `prompts/extract.md`

Recommended changes:

- Product-login exclusion.
- Interface-scoped authentication.
- Stronger OAuth classification examples.
- Clear distinction between API key, bearer token transport, OAuth2, and generic token.
- Require explicit evidence for credential acquisition.

### `prompts/audit.md`

Recommended changes:

- Compare the chosen enum against available alternatives.
- Flag a technically supported description paired with the wrong taxonomy enum.
- Preserve the direct/partial/unsupported output contract unless schema changes are necessary.

### New `src/integration_research/verifier.py`

Keep it direct and bounded. Avoid framework layers.

### `scripts/build_case_study.py`

Recommended changes:

- Do not display `first_pass_structurally_valid` as fully verified.
- Separate failed, needs verification, human review, and verified.
- Do not count incomplete rows as easy wins.
- Label the 60-claim sample as evidence agreement.
- Surface the remaining critical unknown count.

### Tests

Add focused tests rather than broad snapshots.

## Required regression tests

### Authentication tests

1. Product login does not establish API OAuth2.
2. Dedicated OAuth authorization-code documentation maps to OAuth2.
3. Bearer transport does not create a separate token method when OAuth2 is established.
4. Admin-generated workspace access token can map to API key when official docs call it an API key.
5. Unknown cannot coexist with known auth methods.
6. Auth evidence must identify the relevant developer surface.

### Source-selection tests

1. Select two distinct high-quality authentication sources when available.
2. A generic homepage loses to a developer authentication page.
3. A homepage containing only “robust API” fails the API-surface quality gate.
4. Trusted developer subdomains remain eligible.
5. Shared GitHub host still requires the correct repository path.
6. Follow-up search activates when a critical role remains weak.

### Completeness tests

1. Unknown authentication makes the record `needs_verification`.
2. Unknown credential access makes buildability ineligible for a verified final unless the chosen local path needs no credentials.
3. Homepage-only developer evidence prevents final export.
4. Non-critical unknowns may remain when the usable integration path is completely established.
5. A structurally valid record is not automatically a verified record.

### Verifier tests

1. Verifier receives only disputed fields.
2. It cannot admit an untrusted domain.
3. It stores new sources and a correction diff separately.
4. It stops when its budget is exhausted.
5. Exhausted unresolved cases become `needs_human_review`.
6. Browser Tool is used only after normal search/fetch is insufficient.

### Buildability tests

1. Broad self-serve REST API returns yes.
2. Broad API with admin-created credentials returns conditional.
3. Partner or vendor approval returns conditional.
4. Local CLI with documented local input/output and no account returns yes.
5. Known API with unknown credential acquisition stays unknown or needs verification.
6. A usable private path is not incorrectly blocked by an unrelated marketplace-review unknown.

### Attio regression

Expected minimum:

- Auth contains OAuth2 and API key.
- Each method explains its integration surface.
- Credential access captures the administrator requirement for workspace API keys.
- Official MCP is retained with its OAuth details.
- The row is not based on the normal Google login page.

### Podio regression

Expected minimum:

- Homepage-only evidence cannot produce a verified record.
- Targeted developer-document discovery runs.
- At least one official developer source is fetched before auth or API claims become known.
- If official docs remain inaccessible, the record becomes human review with exact attempted paths.

## Acceptance criteria for the repaired seven-app pilot

Every pilot app must satisfy:

1. Exact identity is correct.
2. Every known material field has official fetched evidence.
3. Authentication is scoped to a developer interface.
4. Product login is not used as API-auth evidence.
5. Credential acquisition is known or explicitly blocks verification.
6. At least one callable integration path is established or explicitly absent.
7. Buildability has a plain-English evidence-backed explanation.
8. Critical unknown fields are zero for verified records.
9. Any unresolved critical field produces `needs_human_review`, not verified.
10. Original and corrected artifacts remain separate.
11. A human can open every cited URL and understand why it supports the field.
12. No app advances merely because its JSON validates.

Specific pass conditions:

- Attio no longer reports `other; api_key` for the stored authorization-code evidence.
- Podio no longer passes using only `https://podio.com/`.
- Mermaid CLI remains buildable through a local no-credential path.
- PitchBook remains gated or conditional when official evidence requires enterprise or sales access.
- Google Ads preserves the difference between OAuth, developer token, customer account, and production review.

## Manual accuracy check

After the seven-app run, create or update a manual gold file that records field-level truth for those seven apps.

For each app, manually verify:

- Identity.
- Authentication methods and surfaces.
- Credential access.
- Production gate.
- API availability and style.
- API breadth.
- Read/write capability.
- MCP status.
- Buildability.
- Evidence URL validity.

Report separately:

- Field-level exact agreement.
- Supported-claim rate.
- Critical-field completeness.
- Unsupported-claim rate.
- Unknown rate.
- Number of verifier corrections.
- Number sent to human review.

Do not report only one combined accuracy percentage.

## Recommended run sequence

### Before live execution

Run deterministic checks:

```bash
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy src tests
uv run --frozen pytest
```

Confirm no secrets or generated artifacts are tracked:

```bash
git status --short
git ls-files .env .state runs
```

Do not print keys or session headers.

### Live pilot, only when explicitly authorized

Suggested command shape after implementation:

```bash
uv run --frozen research run --ids 4,6,22,31,61,90,98 --run-id accuracy-pilot-v1
```

If verification becomes a separate command:

```bash
uv run --frozen research verify --run-id accuracy-pilot-v1 --critical
```

The exact CLI may differ, but the behavior must remain bounded and auditable.

### Inspection before scale

For every pilot app, inspect:

```text
searches.json
selected-sources.json
sources/
draft.json
semantic-audit.json
admission-diff.json
completeness.json
verification/
verified-final.json
report.json
```

Only after manual inspection should the remaining apps run in batches.

## Failure-handling policy

### Search failure

- Preserve the raw error.
- Retry only within a small budget.
- Use a more focused query rather than repeating the same query unchanged.

### Weak search results

- Do not fail immediately if only the catalog homepage is selected.
- Mark the role weak.
- Run targeted official-document discovery.

### Fetch failure

- Preserve the failed URL, status, and raw response.
- Try one alternative official source.
- Use Browser Tool only when the page is public but fetch is blocked, JavaScript-heavy, or navigation-dependent.

### Model extraction failure

- Preserve the raw response metadata.
- Do not silently coerce invalid enums.
- Retry once only if the failure is transient or formatting-related.

### Evidence conflict

- Preserve both official sources.
- Route only the disputed field to the stronger verifier.
- Do not let the verifier rewrite unrelated fields.

### Budget exhaustion

- Mark `needs_human_review`.
- List attempted searches and URLs.
- State exactly which critical field remains unresolved.
- Do not fabricate a final value.

## Things the next LLM must not do

1. Do not manually fill all 100 rows from prior knowledge.
2. Do not use OpenAI web search as evidence.
3. Do not classify API auth from a customer login screen.
4. Do not solve unknowns by lowering evidence standards.
5. Do not call a record accurate merely because Pydantic accepts it.
6. Do not overwrite first-pass artifacts during correction.
7. Do not trust arbitrary third-party domains because a model says they are official.
8. Do not run an unbounded browser agent for every app.
9. Do not add a new framework when direct Python is enough.
10. Do not rerun all 100 before the repaired pilot passes.
11. Do not report the 60/60 evidence sample as global 100-app factual accuracy.
12. Do not claim that `not_found` proves no MCP exists anywhere.
13. Do not infer no production review from silence.
14. Do not commit live credentials or generated run contents.

## Decisions that should remain deterministic

The model may propose values, but code should decide:

- Whether a domain is trusted.
- Whether evidence IDs exist.
- Whether quotations occur in stored source text.
- Whether required critical fields are complete.
- Whether a record can be exported as verified.
- Which buildability rule applies to known facts.
- Whether budgets are exhausted.
- Whether original artifacts remain immutable.

## Decisions where a model is useful

A model is useful for:

- Mapping varied documentation wording into the schema.
- Comparing official pages that describe different integration paths.
- Identifying which quoted passages support a field.
- Recognizing partial support or overstatement.
- Proposing focused follow-up queries for a specific unresolved field, if deterministic templates are insufficient.
- Producing a concise explanation after deterministic admission.

The model should not be the final authority for trust, evidence existence, completeness, or buildability.

## Suggested one-shot instruction for the implementing LLM

The following prompt can be given together with this document:

```text
Read AGENTS.md, docs/COMPOSIO_TAKEHOME_CONTEXT.md, and
docs/ACCURACY_REPAIR_LLM_HANDOFF.md completely before editing.

Repair the existing Phase 1 pipeline for accuracy without redesigning the repository.
Preserve the current evidence, validation, audit, buildability, and immutable-artifact
foundations.

Implement, in priority order:

1. A deterministic completeness gate that separates structurally valid first-pass
   records from verified records. Critical unknowns must become needs_verification.
2. Multi-page selection for authentication, credential access, and API surface,
   plus a post-fetch quality gate that rejects generic homepage marketing as
   sufficient developer evidence.
3. One bounded targeted follow-up research pass for unresolved critical fields,
   using Composio Search and Fetch. Use Browser Tool only as a bounded fallback.
4. A real verifier/correction path that preserves first-pass and corrected artifacts
   separately and only changes disputed fields.
5. Stronger interface-scoped authentication rules so product login is not confused
   with API auth and Attio's documented authorization-code path is not labeled other.
6. Honest export and case-study statuses. Do not present incomplete records as final.

Add focused tests for Attio and Podio and run the seven-app pilot IDs
4,6,22,31,61,90,98 only after deterministic checks pass and live execution is
explicitly authorized.

Do not run all 100 apps. Do not lower evidence standards. Do not add frameworks,
a database, Playwright, or a frontend. Keep the implementation direct and bounded.

Before editing, inspect the current code and write a short file-specific plan. After
editing, run uv sync --frozen, ruff check, ruff format --check, mypy, and pytest.
Report verified behavior, remaining unknowns, and any owner-run live acceptance still
required separately.
```

## Minimum acceptable result under extreme time pressure

If the full verifier cannot be completed, the minimum defensible submission is:

1. Rename the current output as first-pass and incomplete.
2. Add a completeness gate.
3. Improve retrieval to two pages for critical roles.
4. Add one targeted follow-up query for critical unknowns.
5. Add Attio and Podio regression tests.
6. Run and manually inspect only the seven-app pilot.
7. Update the case study to report verified, needs verification, human review, and failed separately.
8. Remove any broad accuracy implication not backed by manual gold.

This smaller result is stronger than another 100-app run that reproduces inaccurate or unknown-heavy rows.

## Stronger result if time allows

After the minimum result:

1. Add the bounded Composio MCP verifier.
2. Add Browser Tool fallback.
3. Add path-specific buildability explanations.
4. Add a 12-to-20-app field-level manual gold comparison.
5. Rerun the remaining apps in batches with stop conditions.

## Stop conditions for the full run

Stop and inspect rather than continuing when any of these occur:

- More than 20% of a batch has unknown credential access.
- More than 20% of a batch has unknown authentication.
- Any record is verified from homepage-only developer evidence.
- Any product-login page is used to classify API auth.
- The verifier changes unrelated fields.
- Browser calls become unbounded.
- A trusted-domain exception is added without deterministic catalog or official-link evidence.
- Attio regresses to `other` for the documented authorization-code path.
- Podio again reaches final output using only its homepage.

## Definition of done

The accuracy repair is complete only when:

- The seven-app pilot passes the stated acceptance criteria.
- Attio and Podio regression tests pass.
- Critical unknowns cannot be presented as verified.
- Weak source roles trigger targeted follow-up research.
- The real verification path gathers new evidence or explicitly escalates to human review.
- First-pass and corrected artifacts remain separate.
- Buildability includes an understandable evidence-backed path and blocker.
- The case study distinguishes evidence agreement from factual accuracy.
- All deterministic repository checks pass.
- No secrets or generated live run artifacts are tracked.
- The remaining 93 apps have not been rerun until the pilot is manually inspected.

## Final perspective

The current system's biggest strength is disciplined abstention: it prefers unknown over unsupported claims. Its biggest weakness is treating abstention as the end of research rather than the trigger for targeted evidence recovery.

The repair should not make the model more confident. It should make the system better at finding the right official pages, associating facts with the correct integration surface, and refusing to label incomplete research as final.

The most valuable one-shot improvement is therefore:

```text
strong first-pass evidence
    -> deterministic completeness check
    -> targeted follow-up retrieval for critical gaps
    -> bounded evidence-gathering verifier
    -> deterministic admission and buildability
    -> verified, human-review, or failed status
```

That preserves the repository's precision-first design while making the output useful under a tight deadline.
