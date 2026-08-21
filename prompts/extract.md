# Integration research extraction

Prompt version: `catalog-extract-v3`

Extract integration facts about the named catalog app from the supplied fetched sources.

## Evidence boundary

- Use only supplied source content. Do not use prior knowledge, browse, or ask for tools.
- Cite evidence only with a supplied `source_id` and `snippet_id`; never return a URL or write your
  own quotation. A snippet ID resolves deterministically to exact stored source text.
- Every evidence reference must pair a snippet with its own source. Do not invent snippet IDs.
- Every known material claim needs evidence whose quotation appears in its source.
- Return the appropriate enum `unknown`, nullable text value, or empty API-style list when the
  sources do not establish a claim. Add a specific unresolved question for every material unknown.
- Do not decide buildability or integration paths.

## Authentication

- Use only these high-level methods: `oauth2`, `api_key`, `basic`, `token`, `other`, `none`, and
  `unknown`.
- Preserve implementation detail, such as “personal access token” or “application JWT,” in
  `details`. Do not create a second method for the Authorization transport scheme.
- OAuth2 requires text explicitly establishing OAuth 2.0 or dedicated OAuth application
  documentation. The words “OAuth token” alone are insufficient.
- Only classify authentication used by a developer interface. Normal product login, Google login,
  email login, SAML login, or employee single sign-on is not API authentication evidence.
- State the integration surface in `details`: REST API, GraphQL API, public app, private workspace
  integration, hosted MCP, or local CLI.
- Dedicated OAuth application documentation that establishes an authorization-code flow, client
  ID, client secret, authorization endpoint, token endpoint, and bearer access token maps to
  `oauth2`.
- Do not add `token` merely because an OAuth access token is transported as a bearer token.
- Do not classify a client ID and client secret as `api_key` unless the documentation calls it an
  API key or describes an equivalent static key.
- A fully local CLI or library path may use `none` authentication and `not_required` credential
  access when the source positively documents installation plus a command or function operating on
  local inputs and outputs without an external account or service. Cite that local invocation. Do
  not use this rule for a remote-service CLI merely because credentials are omitted from one example.

## Access and gating

- `credential_access` describes how credentials are obtained.
- `commercial_requirement` separately describes whether free, trial, paid, or enterprise access is
  required. Credential creation alone does not prove `free_available`.
- `production_gate` separately describes approval. `none` is a positive claim and requires direct
  evidence that no review or approval is required. Silence means `unknown`.

## Interfaces

- `api_styles` may contain only REST, GraphQL, RPC, or another callable API style.
- Webhooks are an event interface, SDKs are client libraries, and a CLI is a local execution path.
  Record them only in `webhooks`, `official_sdk`, and `cli`; never put them in `api_styles`.
- Mark `cli = yes` only when the source documents a usable command-line operation, not merely a CLI
  installation reference.
- API breadth is broad only when evidence establishes coverage across most important resources,
  moderate for useful but incomplete coverage, narrow for one constrained workflow, none only with
  explicit negative evidence, and otherwise unknown.
- `not_found` for MCP is a bounded search result, never universal proof of non-existence.
- Do not infer any `no`, `none`, or `not_found` value from silence or failed search.

Keep `app_id`, `app_name`, and `category` exactly as supplied. Return only the structured response.
