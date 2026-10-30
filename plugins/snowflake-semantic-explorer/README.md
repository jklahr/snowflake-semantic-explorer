# Snowflake Semantic Explorer

A Claude plugin for exploring and analyzing Snowflake data through governed definitions: your business ontology, your semantic views and your certified metrics. It needs a Snowflake MCP server connected to Claude. It does not need anything hosted.

- **Explore**: which domains, concepts and semantic views exist, and what they mean.
- **Analyze**: numbers from certified metrics, with the governed definition, the view and the path taken.
- **Dashboards**: one self-contained, interactive HTML file with KPI sparklines and period-over-period change, page filters you can add and remove, info popovers with definitions and the governed query, "Explain this data" buttons, and tiles you can edit.
- **Deep dives**: hypothesis-driven investigations that follow the ontology's relationships.

## Requirements

1. **A Snowflake MCP server connected to Claude**, signed in with Snowflake OAuth. A standard Snowflake-managed MCP server works; the skills use its dedicated semantic-view and ontology tools if it has them, and SQL and Cortex Analyst tools if it does not (see `skills/explore-data-estate/references/snowflake-tools.md`).
2. **Somewhere Claude can run Python 3.9+ and write a file**, for dashboards only. That is built in to claude.ai and Cowork with code execution on, and to Claude Code with `python3` installed. Without it, Claude answers inline with charts instead of building a dashboard file.

## What is in the box

```
.claude-plugin/plugin.json          manifest
skills/explore-data-estate          domains, concepts, views (start here)
skills/analyze-domain               governed numbers and explanations
skills/semantic-dashboard           builds the dashboard file (script + page template)
skills/deep-dive                    investigations that follow ontology relationships
agents/deep-dive-analyst.md         subagent for long investigations
commands/                           /explore  /dashboard  /deep-dive
docs/mcp-server-requirements.md     optional server improvements
```

## Install

Claude Code: `/plugin marketplace add <your-org>/<repo>` then `/plugin install snowflake-semantic-explorer@snowflake-semantic-explorer-marketplace`.
claude.ai and Cowork: an organization owner adds the marketplace under Organization settings > Plugins. See the repository README.

## Use it

- "What data do we have on revenue?" (explore)
- "How is FY2026 net revenue tracking against budget by brand?" (analyze)
- "Build me a dashboard for the P&L view" (dashboard)
- "Why is Wildflower Organics so far under budget?" (deep dive)

Or `/explore`, `/dashboard`, `/deep-dive`.

## How it answers

Claude starts from business meaning: it lists the ontology domains and asks which to use, finds the concept (governed definition, formula, and the policies that apply), takes the semantic view the concept is bound to, and gets the number with `query_semantic_view`. For "why" questions it follows the concept's relationships, at most three hops. Answers name the view, the metric and the path taken. Without an ontology it works from semantic views directly.

## How dashboards work

Claude queries the view, writes the results and a small JSON spec into files, and runs `skills/semantic-dashboard/scripts/build_snapshot.py`. The script validates everything, checks the copied numbers against independent totals (per grand total, per period and per category) and refuses to build if they do not match, then writes one HTML file with the data inside. The file works offline and loads nothing from the internet.

## Limits

- A dashboard is a **snapshot**: it shows the data as of the build and does not refresh. Ask Claude to rebuild for fresh numbers. The file contains the data, so share it like the data.
- Claude writes each row out, so about 500 rows is comfortable (50,000 is the hard limit). Tiles whose data lacks a filtered field say so.
- Edits made in the page are kept in that browser only.
