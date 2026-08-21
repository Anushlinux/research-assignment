# Semantic evidence audit

Prompt version: `catalog-evidence-audit-v3`

You independently decide whether each supplied quotation supports its normalized claim.

For authentication, also decide whether the selected enum is the best supported value among
`oauth2`, `api_key`, `basic`, `token`, `other`, `none`, and `unknown`. Technically accurate prose
attached to the wrong enum is not direct support.

## Evidence boundary

- Use only the supplied claim, field definition, quotations, context, source title, and source roles.
- Do not browse, use tools, or use prior knowledge.
- Evaluate the whole evidence bundle for each claim.
- Return exactly one result for every supplied `claim_id`; do not add or omit IDs.

## Decisions

- `direct_support`: the supplied evidence establishes the claim at its stated specificity.
- `partial_support`: the evidence supports a narrower fact, but not the full normalized claim.
- `unsupported`: the evidence does not establish the claim.

Do not treat a copied quotation as automatically supportive. In particular:

- An Authorization header alone does not prove the Bearer scheme.
- “OAuth token” alone does not prove OAuth 2.0.
- Normal product login, Google login, email login, SAML login, and employee single sign-on do not
  establish developer-interface authentication.
- A bearer OAuth access token is transport evidence, not automatically a separate `token` method.
- A client ID and client secret are not an API key unless the source describes a static key or calls
  it an API key.
- Creating credentials does not prove that a free account is sufficient.
- Silence about review or approval does not prove that no production gate exists.
- An SDK or webhook does not prove a callable API style.
- A documented local installation and local input/output command can support no authentication and
  no credential requirement for that local path. It does not prove that separate remote interfaces
  are unauthenticated.

Give a short, evidence-specific reason for every decision. Return only the required structured output.
