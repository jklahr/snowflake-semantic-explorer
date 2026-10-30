---
name: analyze-domain
description: Answer analytical questions on Snowflake data from governed definitions and certified metrics. Use whenever the user asks for numbers, trends, comparisons, breakdowns, variances, "what is X", "why did X change", top-N, or year-over-year questions about business data in Snowflake, even if they do not mention semantic views or the ontology. Use before building a dashboard to understand the data. Load this before the first query of any Snowflake conversation; it contains the answer format, including the required chart and "path walked" close.
---

# Analyze a domain from governed definitions

snowflake-semantic-explorer v0.6.0

> Tool names, argument formats and fallbacks are in `../explore-data-estate/references/snowflake-tools.md`. The list arguments of `query_semantic_view` are JSON **strings**; read that file before the first query.

Answer from governed definitions and certified metrics. The ontology says what a concept means and which data object implements it; a semantic view produces the number.

When Snowflake semantic-view tools are available, use this skill instead of the generic `analyze`, `explore-data`, `write-query`, or `sql-queries` skills. Use inline chart tools for answers. Use `create-viz` only when the user asks for a downloadable or publication-quality figure.

## Workflow

1. **Choose the domain** (skip if the user named it or you already know it). With `business_ontology`, list domains with an empty call, show them, and ask which to use. Search only that domain.
2. **Find the concept.** Short search term, best match (prefer ACTIVE metrics). Read `description`, `formula`, `relationships`, `assets`, and the policy concepts that apply. Prefer an asset whose type is `Semantic View`. If that asset has `fqn` null, do not treat it as unbound: match the domain and concept against view comments. If no matching view is visible, stop and say it is likely a grants or visibility gap. Use a table or column only when no view is bound, and say why.
3. **Know the view.** Call `describe_semantic_view` for every view you will query (retry once, then the SQL fallback). Work only with names it returns, including its `filters` array. Read each metric's expression so you know what can be summed and what is a ratio.
4. **Get the number.** Call `query_semantic_view`. This is the default for every number you will report. To change the cut, call it again with one argument changed. Never write the statement yourself and never pass SQL. Use `ask_semantic_view`, or `ask_governed` with `RUN_TYPE` `sv`, only when a certified query cannot express the question, then re-run quoted figures through `query_semantic_view`. If the follow-up asks why a number moved or where a gap comes from, stop and read `deep-dive` before running more queries.
5. **Use the ontology for domain discovery.** Stay in the chosen domain. For "what drives this" or "why did this change", go to step 8.
6. **Mind scenario and scope traps.** The metric an ontology asset names may sum all scenarios together; use the Actual-scoped twin or filter the scenario, as the concept's policies direct, and say which. Prefer explicitly scoped metrics (`ACTUAL_...`, `BUDGET_...`). Periods that have a plan but no actuals return zeros; say the data ends at the last populated period. Metrics from different entities may use different scopes. When you compare them, say so and show that the two agree within a stated tolerance.
7. **Check before reporting.** Do the parts add to the total? Reconcile one grouped query against one ungrouped query (the grouped dollars must equal the total). Does the number agree with the concept's formula?
8. **Follow relationships for drivers.** Take `relationships.edges` and resolve term ids through `nodes`. The drivers of X are the sources of `DERIVES` edges pointing at X and the terms that "reduce" it. `HAS_VARIANT` gives plan and forecast twins. Visit each neighbor in the same domain, then run its bound semantic view. **Stop at three hops** unless the user asks for more. Do not join two objects unless a relationship connects their concepts. For a long investigation use `deep-dive`.
9. **When the curated data cannot answer, check Cortex Sense before offering it.** Call `list_governed_catalog` at most once. If `senses` is empty, say none are configured and do not make the offer. If at least one exists, ask: "Do you want me to use Cortex Sense to look further? Those results are not certified or curated. They search a broader set of data." On yes, call `ask_governed` with `RUN_TYPE` `sv_ontology_sense`, the same views and domain, and that sense in `SENSES`. Cite the sense, the document or table, and the definition or SQL, and label it exploratory.

## Answer format

1. **Governed definition.** Say plainly when the ontology has none.
2. **The number**, naming the semantic view and the metric. If you used a table instead of a view, say why. Keep the statement `query_semantic_view` returned.
3. **Chart**, when the Charts section requires one. Place it after the lead finding.
4. **Path walked:** concept, edge, concept, and the objects each pointed at. Name any concept that had no data bound to it.

Lead with the finding, then support it with 2 to 4 numbers. Separate what the data shows from your interpretation. Do not write "probably" or "likely" about something one more governed query can settle: run the query.

## Charts (required)

Every answer that reports three or more numbers, or compares across a dimension or period, includes at least one chart. Place it directly after the lead finding, before the supporting prose. One chart per distinct finding; at most three per answer. Do not chart a single number. Do not repeat the same numbers in a table unless there are more than twelve rows.

Tool choice:

- `chart_display_v0` for plain line, grouped bar, and scatter charts, up to 12 series.
- The host's visualizer (`show_widget`) for stacked bars, waterfalls, annotated charts, diverging bars, and small multiples.
- If neither tool is available, give a compact table and say a chart could not be drawn.

| Finding | Chart |
|---|---|
| Variance or gap vs plan or last year, by a dimension | bar of the gap, negative values visible, sorted by gap |
| Bridge (comp vs total, price vs volume, rate vs mix) | waterfall, or grouped bars of the components |
| Trend over time | line, with last year or plan as a second line |
| Ranking or top-N | horizontal bar |
| Driver decomposition (traffic, conversion, ticket) | bars of the percent change of each driver vs last year |
| Composition | stacked bar; avoid pie |

Every chart states the metric, scope, and period in the title, shows units, uses the same sort and the same figures as the confirmed `query_semantic_view` results, and has one line below it naming the view, filters, and any scope difference.

Escalate to `semantic-dashboard` when the user wants to explore, filter, share, or revisit the data. Escalate to `deep-dive` when a number needs a causal explanation.

## Patterns worth knowing

- **Variance:** pair an actual metric with its budget or last-year counterpart. Rank dimension members by dollar contribution, not percent.
- **Retail comps:** run the comp-versus-total bridge (comp change plus new-minus-closed stores) before commenting on the store base.
- **Ratios:** never average ratios across groups. Use a governed ratio metric, or divide the sums of its numerator and denominator.
- **Time:** use the view's own fiscal or calendar dimensions. Compare fiscal period strings with `>=` and `<=`.
