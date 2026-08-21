# Prompts

`extract.md` is the versioned prompt for tool-free structured extraction over
deterministically generated evidence snippets from fetched catalog-trusted sources. `audit.md`
independently checks claim-to-evidence support without tools or browsing.

The bounded recovery pass reuses these prompts after targeted Composio Search and fetch calls, then
deterministically admits changes only to disputed fields. A future MCP verifier prompt and Browser
Tool fallback remain intentionally separate from this minimum repair.
