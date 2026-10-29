# What the plugin expects from your Snowflake MCP server

The skills are written against these tools. Names can differ; if yours do, edit the tool names mentioned in the `SKILL.md` files. Items marked **Should** are changes we recommend after testing the current server.

## Tools the skills use today

| Tool | Purpose | Used by |
|---|---|---|
| `list_semantic_views` | Enumerate views with qualified name and comment | explore |
| `describe_semantic_view` | Metrics and dimensions of one view | all |
| `query_semantic_view` | Deterministic query by metric and dimension names | analyze, dashboard, deep-dive |
| `ask_semantic_view` | Natural-language question, returns answer, SQL, rows, chart spec | analyze |
| `business_ontology` | Domains and governed concepts bound to views | explore |
| agent run tool (name varies) | Server-side agentic investigation | deep-dive |
| `sql_exec_tool` | Read-only SQL fallback | analyze (last resort) |

## Should: fix metadata resolution

During testing, `describe_semantic_view` and `query_semantic_view` first failed with `Unknown user-defined function <DB>.PUBLIC.DESCRIBE_SEMANTIC_VIEW` (and the query equivalent) when the database and schema were passed, and succeeded on a later identical call. The server appears to resolve its helper functions inside the target database's `PUBLIC` schema. Resolve them from one fixed location, or call `DESCRIBE SEMANTIC VIEW` and `SELECT ... FROM SEMANTIC_VIEW(...)` directly, so behavior does not depend on the target database.

## Should: make read-only tools pre-approvable

Each call currently needs interactive approval and one was declined mid-session, which broke a dashboard build. Mark `list_*`, `describe_*`, `query_*` and `ask_*` as read-only so users or admins can pre-approve them, and keep approval for `sql_exec_tool` and any write-capable tool.

## Should: richer metric metadata in `describe_semantic_view`

The skills have to guess whether a metric is safe to sum. Return, per metric:

- `additive`: true or false (or the aggregation: sum, count_distinct, ratio, snapshot).
- `scenario`: for scoped metrics such as Actual or Budget, the scope; and a flag when a metric is unscoped across scenarios.
- `unit` and `currency`.
- `numerator` and `denominator` for ratios.
- Per dimension: `type` (time, category, id), `cardinality` estimate, and for time dimensions the min and max populated values.

## Should: structured, parameterizable query arguments

`query_semantic_view` takes `METRICS`, `DIMENSIONS`, `FILTERS` as JSON strings. That works for Claude, but it is awkward for any UI or live-refresh path. Accept native arrays and objects, and support named parameters (`{{period_from}}`) so a rendered UI can re-run the same query with different control values.

## Implemented: a UI-returning tool (MCP App)

`render_dashboard` now exists as a reference implementation in the repo's `server/` folder (see `server/README.md`). It returns an interactive dashboard rendered by the client from a `ui://` resource, with live queries through app-only tools, so there is no row transcription and no snapshot limit. To adopt it, implement the five-method `Backend` protocol on top of your existing describe, query and ontology code, then call `register(your_server, Explorer(backend))`. The plugin's `semantic-dashboard` skill already prefers this tool when it is present and falls back to the snapshot script when it is not.

## Agent run tool contract

For deep dives, the skills hand the tool a written brief (question, scope, known facts, hypotheses, desired output). Return a structured result with: answer, ranked drivers with figures, queries executed, and confidence. Make runs resumable or at least return a run id so Claude can poll.

## Auth

The plugin reads `SNOWFLAKE_MCP_URL` and `SNOWFLAKE_MCP_TOKEN` from the environment (see `.mcp.json`). If you use OAuth, register the server as a connector instead and delete `.mcp.json` from the plugin.
