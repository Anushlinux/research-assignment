# Semantic evidence audit

Prompt version: `catalog-evidence-audit-v2`

You independently decide whether each supplied quotation supports its normalized claim.

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
- Creating credentials does not prove that a free account is sufficient.
- Silence about review or approval does not prove that no production gate exists.
- An SDK or webhook does not prove a callable API style.
- A documented local installation and local input/output command can support no authentication and
  no credential requirement for that local path. It does not prove that separate remote interfaces
  are unauthenticated.

Give a short, evidence-specific reason for every decision. Return only the required structured output.
