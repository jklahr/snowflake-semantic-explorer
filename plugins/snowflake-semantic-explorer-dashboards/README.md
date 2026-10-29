# Snowflake Semantic Explorer: live dashboards (optional add-on)

You do **not** need this to use Semantic Explorer. The core plugin already explores, analyzes, builds snapshot dashboards and runs deep dives against your Snowflake MCP server. Add this only if you want live, interactive dashboards inside the chat (page filters, KPI sparklines with period-over-period change, per-tile "Explain with AI", info popovers, in-place editing).

## Requirements
- An administrator has deployed the dashboard server (see `docs/APP_RUNTIME.md` and `server/README.md` in the repository) and given you its URL.
- Your Claude client supports MCP Apps (interactive `ui://` views). If it does not, tools still work but you will see text instead of a dashboard.

## Install
1. Set the server address (Claude Code): `export SEMANTIC_EXPLORER_URL="https://<server-url>/mcp"`.
2. `/plugin install snowflake-semantic-explorer-dashboards@snowflake-semantic-explorer-marketplace`.
3. Sign in when prompted (Snowflake OAuth), then run `/dashboard-check`.

In claude.ai or Claude Desktop, add the server as a custom connector with the same URL instead of using the environment variable.

When this add-on is connected, the core plugin's `semantic-dashboard` skill uses `render_dashboard` automatically; otherwise it builds a snapshot.
