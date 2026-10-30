---
name: deep-dive
description: Investigate why a metric moved or where a variance comes from, using the business ontology's relationship graph to plan the investigation. Use when the user says "why", "what's driving", "root cause", "investigate", "dig into", "drill into/down", "break this down", "what's behind", "softness", "weak", "soft", "down vs last year / plan / budget", "which region, store, product or channel is dragging", or any follow-up that asks to explain a number or variance already shown. Always load `analyze-domain` first. Prefer this over a single query when the answer needs several linked queries.
---

# Deep dive

snowflake-semantic-explorer v0.6.0

> Argument formats, error codes and known-incompatible query combinations are in `../explore-data-estate/references/snowflake-tools.md`, section Troubleshooting. If the sibling data plugin is installed, apply its `validate-data` checklist before presenting (period comparability, denominator shifts, sums to total).

A deep dive breaks a number into its governed drivers and tests explanations against data. Numbers still come from `query_semantic_view`.

## Starting point: a tile's "Explain this data" message

A message that begins with a question and then a block headed "Dashboard context" comes from the dashboard's sparkle button. Treat the question as the brief, the metric and dimension names as exact, the active filters as scope, and the figures as already known. Investigate; do not restate them. Say which filters the answer assumes.

## Procedure (follow in order; do not skip a step)

0. Engine. If `ask_governed` is in the tool list, call it once with `RUN_TYPE` `sv_ontology` and every named argument: `QUESTION`, `RUN_TYPE`, `DB_NAME`, `SCHEMA_NAME`, `VIEW_NAME`, `SEMANTIC_VIEWS`, `ONTOLOGY_DOMAINS`, and `SENSES` as `"[]"`. On any error, retry once, then run the direct walk below yourself. Do not wait for a `deep-dive-analyst` subagent; it may not exist. Say in one sentence which engine you used and why. If the procedure fails twice, do not retry a third time.
1. Brief. Write the question, the scope (view, metric, period, filters) and what is already known, so queries are not repeated.
2. Find the concept for the metric in the chosen ontology domain. Then search the same domain for "<metric> driver tree", "<metric> bridge" and "root cause". A term named "...Driver Tree" with `HAS_PART` edges is the governed hypothesis list: its children are the first hop. A term named "...Bridge" is a required check (step 5).
3. Walk the graph, at most three hops. Hop 1 is a direct neighbour of the metric. Follow `DERIVES` where the visited concept is the target (sources are drivers), `HAS_PART` children of a driver-tree term, `CUSTOM` edges labelled "drives" or "reduces", and `RELATED_TO` bridge or driver-tree terms. Read `APPLIES_TO` only to apply policy concepts. For each node record the hop, concept, bound view and metric (or UNBOUND), and the this-year vs last-year result. A node with no upstream edges is a leaf: say "the governed graph ends here".
4. Query each bound driver for the same scope, this year vs last year, one cut per call. Decompose by the dimension the user cares about. Rank by contribution to the gap in dollars or units, not by percent change.
5. Run the bridge if one exists (for example comp vs total: total change = comp change + new minus closed stores) before attributing the gap to existing locations. Do not infer direction from a hunch; query it.
6. Test the strongest explanation with a second, independent cut (a different grain or a different metric). Rule out partial periods, scope differences between metrics, and last-year alignment.
7. Stop when the top drivers explain most of the gap or more queries stop changing the answer. If the graph is exhausted and the cause is still unexplained, say so. Offer Cortex Sense only if `list_governed_catalog` returns at least one sense. If `senses` is empty, say none are configured and do not make the offer. On yes, call `ask_governed` with `RUN_TYPE` `sv_ontology_sense`. Label that result exploratory, cite the sense, the document or table, and the definition or SQL, and do not treat it as a certified driver.

## Report

Every deep-dive answer has these parts, in this order:

1. Answer: one or two sentences.
2. Chart of the ranked contributions or the bridge. See Charts in `analyze-domain`.
3. Ranked drivers: driver, impact in dollars or units, share of the gap, source `view.metric`.
4. Graph walked: concept, edge, concept per hop, with bound `view.metric`, the UNBOUND concepts, and any leaf where the governed graph ends.
5. Ruled out: what was tested and found flat or irrelevant, with the figure.
6. Limits: what the data cannot say. Keep correlation and causation separate.
7. Next steps, and an offer to add the finding to the dashboard.

If part 4 is empty, the investigation did not happen. Say so instead of presenting the result as a deep dive.
