---
name: analyze-domain
description: Answer analytical questions on Snowflake data from governed definitions and certified metrics. Use whenever the user asks for numbers, trends, comparisons, breakdowns, variances, "what is X", "why did X change", top-N, or year-over-year questions about business data in Snowflake, even if they do not mention semantic views or the ontology. Use before building a dashboard to understand the data.
---

# Analyze a domain from governed definitions

> Tool names, argument formats and fallbacks are in `../explore-data-estate/references/snowflake-tools.md`. The list arguments of `query_semantic_view` are JSON **strings**; read that file before the first query.

Answer from governed definitions and certified metrics. The ontology says what a concept means and which data object implements it; a semantic view produces the number.

## Workflow

1. **Choose the domain** (skip if the user named it or you already know it). With `business_ontology`, list domains with an empty call, show them, and ask which to use. Search only that domain.
2. **Find the concept** the question is about: short search term, best match (prefer ACTIVE metrics). Read `description` (the governed definition), `formula`, `relationships` and `assets`, and the policy concepts that apply to it. Prefer the asset whose type is `Semantic View`; use a table or column only when no view is bound, and say why. With no ontology, pick the view as in the `explore-data-estate` skill.
3. **Know the view.** Call `describe_semantic_view` for every view you will query (retry once on failure, then use the SQL fallback). Work only with names it returns. Read each metric's expression so you know what can be summed and what is a ratio.
4. **Get the number.** Call `query_semantic_view` with metric and dimension names from that description. To change the cut, call it again with one argument changed. Never write the statement yourself and never pass SQL. Use `ask_semantic_view` only for exploration or for a question the certified query cannot express (prefer a defined metric, written `AGG(metric)`); re-run the figures you will quote through `query_semantic_view`.
5. **Mind scenario and scope traps.** The metric an ontology asset names may sum all scenarios together; use the Actual-scoped twin or filter the scenario, as the concept's policies direct (`../explore-data-estate/references/snowflake-tools.md`, step 7 of the ontology section), and say which. Prefer explicitly scoped metrics (`ACTUAL_...`, `BUDGET_...`). Periods that have a plan but no actuals return zeros; say the data ends at the last populated period. If a result looks too small, check the row limit.
6. **Check before reporting.** Do the parts add to the total? Reconcile one grouped query against one ungrouped query. Does the number agree with the concept's formula?
7. **Follow relationships for "what drives this" or "why did this change".** Take the concept's `relationships.edges` (resolve term ids through `nodes`). The drivers of X are the sources of `DERIVES` edges pointing at X and the terms that "reduce" it; `HAS_VARIANT` gives its plan and forecast twins. Visit each neighbor with `business_ontology` (same domain), then run its bound semantic view the same way. **Stop at three hops** unless the user asks for more. Do not join two objects unless a relationship connects their concepts. For a long investigation use the `deep-dive` skill.

## Answer format

1. **Lead with the governed definition**, and say plainly when the ontology has none.
2. **The number**, naming the semantic view and the metric, and the object you queried. If you used a table instead of a view, say why. Keep the statement `query_semantic_view` returned available if the user asks how it was produced.
3. **Close with the path you walked:** concept, relationship, concept, and the objects each pointed at. Name any concept that had no data bound to it.

Lead with the finding, then support it with 2 to 4 numbers. Separate what the data shows from your interpretation.

## Showing results

For a small result, use an inline chart. Escalate to the `semantic-dashboard` skill when the user wants to explore, filter, share or revisit the data. Escalate to the `deep-dive` skill when a number needs a causal explanation.

## Patterns worth knowing

- **Variance:** pair an actual metric with its budget counterpart and compute the gap in your reply.
- **Ratios:** never average ratios across groups. Use a governed ratio metric, or divide the sums of its numerator and denominator.
- **Time:** use the view's own fiscal or calendar dimensions. Do not guess date logic. Compare fiscal period strings with `>=` and `<=`.
