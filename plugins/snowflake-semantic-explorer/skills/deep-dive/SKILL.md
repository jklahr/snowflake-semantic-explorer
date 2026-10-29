---
name: deep-dive
description: Run an agentic deep dive that investigates why a metric moved, where a variance comes from, or what is driving an anomaly in Snowflake data. Use when the user asks "why", "what's driving", "root cause", "investigate", "dig into", or when a dashboard or analysis surfaces a surprising number that needs explanation. Prefer this over a single query when the answer needs several linked queries.
---

# Deep dive

> **Tool names.** The tool names below (for example `describe_semantic_view`) are the common ones. If your server names them differently or lacks one, read `../explore-data-estate/references/snowflake-tools.md` for the equivalent tool or SQL.

A deep dive is a hypothesis-driven investigation: break a number into its drivers, test explanations against data, and return a conclusion with evidence. It runs on top of the same governed metrics as ordinary analysis.

## Starting point: a tile's "Explain this data" message

A message that begins with a question and then a block headed "Dashboard context" comes from the dashboard's sparkle button. Treat the question as the brief, the metric and dimension names as exact, the active filters as scope, and the figures as already known. Do not just restate them; investigate. Use `ask_semantic_view` on the view named in the context, with the current filter values written into the question in plain words, to find candidate explanations, then confirm every figure you quote with `query_semantic_view`. Say which filters your answer assumes.

## Choose the engine

1. **Server-side agent run tool (preferred when present).** If the Snowflake MCP server exposes an agent tool (commonly named `agent_run` or similar; check the tool list), hand it a precise investigation brief and let it plan and execute against the semantic views it can reach. Use this for long, multi-step work or when the user wants Snowflake-governed execution and audit.
2. **Local investigation with the `deep-dive-analyst` subagent.** If there is no agent tool, or you want the investigation kept out of the main conversation, delegate to the subagent. It uses `query_semantic_view` and `ask_semantic_view` directly.

Tell the user which engine you chose and why, in one sentence.

## Let the ontology plan the investigation

If a business ontology exists, start the plan from it instead of guessing hypotheses. Find the concept for the metric in question (search only the chosen domain), then read its `relationships.edges`: what it derives from, measures, or is part of. Each neighbour is a candidate driver. Visit each with `business_ontology` (same domain) and query its bound semantic view the same way. **Stop at three hops** unless the user asks for more, and do not join two objects unless a relationship connects their concepts. Name any concept that had no data bound to it; that is a finding too. Put this walk, and the views it points at, into the brief or the subagent's instructions.

## Writing the brief

A good brief is specific. Include:

- **Question:** one sentence, for example "Why is FY2026 YTD net revenue 4.8% under budget?"
- **Scope:** view, metric, period and any filters already established.
- **What is already known:** numbers from the dashboard or earlier queries, so work is not repeated.
- **Hypotheses to test:** for example customer concentration, one brand underperforming, trade spend rate, seasonality, price versus volume.
- **Output wanted:** ranked drivers with their share of the gap, supporting figures, and confidence.

## Method for the investigation

1. Decompose the metric along each major dimension and rank contributions to the gap or change.
2. Drill into the top contributor and repeat one level down.
3. Test the strongest explanation with a second, independent cut of the data.
4. Rule out data artifacts: partial periods, scope differences, double counting.
5. Stop when the top drivers explain most of the movement, or when more queries stop changing the answer.

## Reporting

Return: the answer in one or two sentences; a ranked list of drivers with figures; what you ruled out; limits of the evidence; and suggested next steps. Keep correlation and causation separate. If the data cannot explain the movement, say so rather than inventing a story.

Offer to add the key finding to the dashboard through the `semantic-dashboard` skill, as a note on the relevant chart.
