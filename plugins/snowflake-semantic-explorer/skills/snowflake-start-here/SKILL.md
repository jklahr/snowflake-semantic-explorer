---
name: snowflake-start-here
description: Read this FIRST, before any other Snowflake skill and before the first query, whenever Snowflake semantic-view or ontology tools (`query_semantic_view`, `business_ontology`, `list_semantic_views`) are available and the user asks anything about business data: numbers, trends, comparisons, breakdowns, variances, "how are we doing", "drill into", "why", "what's wrong", dashboards, or which data exists. It routes to the right skill and sets rules every Snowflake answer must follow.
---

# Start here

snowflake-semantic-explorer v0.6.0

Load the skills in the table before the first query. When Snowflake semantic-view tools are available, use these skills instead of the generic `analyze`, `explore-data`, `build-dashboard`, `write-query`, and `sql-queries` skills.

| User intent | Load, in order |
|---|---|
| "What data do we have", "which view" | `explore-data-estate` |
| Any number, trend, comparison, breakdown, "how are things" | `analyze-domain` |
| Why, what's driving, drill into, break down, what's soft, weak, down, or off vs last year, plan, or budget; which region, store, product, or channel is dragging | `analyze-domain`, then `deep-dive` |
| Dashboard, scorecard, "something I can share or filter" | `analyze-domain`, then `semantic-dashboard` |

Invariants:

- Say in one line which skills you loaded.
- Numbers come only from `query_semantic_view`; never write or pass SQL for governed metrics.
- Any answer with three or more numbers or a comparison includes a chart (see Charts in `analyze-domain`).
- Close every analytical answer with the path walked and any unbound concept (see the answer format in `analyze-domain`).
- Do not write "probably" or "likely" about something one more governed query can settle: run the query.

`statistical-analysis` from a sibling data plugin is only for when the user asks whether a difference is significant. `validate-data` is a pre-delivery check for a deep dive, not a replacement for these skills.
