# Composio tool schemas

These files are the exact CLI-facing input schemas observed during Milestone 0 on
2026-08-21. They were fetched from the authenticated Composio CLI; they are not inferred
from documentation or examples.

## Observed versions

- Composio CLI: `0.3.1`
- Composio Python SDK: `0.20.0`
- Composio Search tool version: `20260618_00`
- Browser Tool version: `20260813_00`
- Native Codex plugin: `0.2.3`

## Commands used

```bash
~/.local/bin/composio execute COMPOSIO_SEARCH_WEB --get-schema
~/.local/bin/composio execute COMPOSIO_SEARCH_FETCH_URL_CONTENT --get-schema
~/.local/bin/composio execute BROWSER_TOOL_CREATE_TASK --get-schema
~/.local/bin/composio execute BROWSER_TOOL_WATCH_TASK --get-schema
~/.local/bin/composio execute BROWSER_TOOL_GET_SESSION --get-schema
```

Each JSON file preserves the `version` and `inputSchema` object cached by the CLI after
the corresponding command completed successfully. Machine-local `schemaPath` values are
intentionally omitted because they are not part of the tool input contract.
