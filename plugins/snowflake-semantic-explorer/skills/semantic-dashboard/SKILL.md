---
name: semantic-dashboard
description: Build an interactive dashboard from a Snowflake semantic view and give the user a file or link to open. The page has KPI tiles with sparklines and period-over-period change, charts, a table, page filters the user can add and remove (checklists for short lists, formulas for long ones), info popovers with definitions, "Explain this data" buttons, and tiles the user can edit. Use whenever the user asks for a dashboard, scorecard, KPI page, report they can explore or share, "visualize this view", or wants filters and drill-downs on Snowflake data, even if they only say "show me this as a dashboard". Also use to change or extend a dashboard built earlier.
---

# Semantic dashboard

> Tool names are the common ones; if your server differs, see `../explore-data-estate/references/snowflake-tools.md`.

There are three ways to deliver this. **Check your tool list first and never ask the user which tier they have.**

| Path | When | What the user gets |
|---|---|---|
| **A. Live** | a `render_dashboard` tool exists | a live dashboard inside the chat |
| **B. Snapshot** (the normal case) | no `render_dashboard`, and you can run Python and write files | one HTML file, fully interactive, data embedded |
| **C. Quick look** | the user only wants one or two numbers or one chart, or you cannot write files | an inline chart and a sentence |

## Path A: live (`render_dashboard` is available)

1. Call `describe_semantic_view` so you know exact names, then `render_dashboard(view=...)`. Omit `tiles` to accept defaults; pass `metrics`, `dimensions`, `time_dimension`, `pop` (`MoM`, `WoW`, `QoQ`, `YoY`, `DoD`, `none`), `filters` or `tiles` when the user told you what they want.
2. Say in one or two sentences what is on it and how to use it (filters on top, ✦ to ask you about a tile, ⓘ for definitions, pencil to edit). Remember `dashboard_id` and the tile ids.
3. For changes call `update_dashboard` with operations (`set_title`, `add_tile`, `update_tile`, `remove_tile`, `move_tile`, `set_filter`, `remove_filter`); call `get_dashboard` first if unsure of the state.
4. If an error names an unknown metric, dimension or operator, fix the call and retry once.

## Path B: snapshot

A snapshot is one self-contained `.html` file. It works offline, needs no hosting and loads nothing from the internet. Everything on the page (filters, period-over-period change, sparklines, popovers, tile editing) runs on the data inside the file. It does not refresh, and anyone who has the file can read that data.

### Steps

1. **Choose the view** (use `explore-data-estate` if the user has not; with an ontology that means choosing the domain, finding the concept and taking its bound semantic view). Call `describe_semantic_view` (retry once, then the SQL fallback). Keep the exact metric and dimension names, their descriptions, the view's comment, and **the fully qualified view that owns each metric** (`catalog.metrics[].view`, needed for inline ask when the dashboard spans several views). **For each metric you will use, look up its concept** in the chosen ontology domain and keep the governed meaning for the info popover: `concept` = the concept name, `definition` = its `description`, `formula` = its `formula`, `source` = the domain name, `bound_to` = the view metric its asset names (`subObjectName`). If you use the Actual-scoped twin of the bound metric (for example `ACTUAL_NET_REVENUE` for a concept bound to `PNL_NET_REVENUE`), still attach the concept to the metric you use and keep `bound_to` as the metric the ontology names, so the popover is honest about the mapping. These go in `definitions.metrics.<NAME>.ontology` (see `references/snapshot-format.md`). If there is no ontology or no match, leave `ontology` out; the view's own description is shown instead. Do not invent definitions.
2. **Decide what the dashboard covers.** Pick up to 4 headline metrics plus the plan or budget counterpart of each (`ACTUAL_X` with `BUDGET_X`), one time dimension, and at most two category dimensions the user would filter by. Prefer metrics that are sums. Read each metric's `EXPRESSION` in the describe output: `SUM(x)` is additive; `SUM(a) / NULLIF(SUM(b), 0)` is a ratio of two additive metrics, so declare it in the catalog with `num` and `den` set to the metrics whose expressions are `SUM(a)` and `SUM(b)` and fetch those two, never the ratio itself. A distinct count or other non-additive metric cannot be re-aggregated under filters: leave it out and tell the user.
3. **Plan the datasets.** A dataset is one query result.
   - *Main dataset:* the time dimension by the category dimensions, with all the metrics. Keep it to **about 500 rows or fewer**: every row has to be written out by you, so use a shorter period window (the last 12 to 24 periods is usually right) or one fewer dimension before you exceed that. Hard limit 50,000.
   - *Optional detail dataset:* a high-cardinality dimension (customers, products) as a **top-N** table, for example the top 25 by the headline metric, with `"partial": true` and a `note` such as `"Top 25 customers by net revenue."` A partial dataset only answers at its own grain, and the page tells the user which filters do not apply to it.
   - Drop future periods that have a plan but no actuals; the builder does this if you set `trim_after_last_actual` to the actual metric.
4. **Query.** Use `query_semantic_view` (list arguments are JSON strings: see `../explore-data-estate/references/snowflake-tools.md`) with scoped metrics (explicitly "actual" or "budget", never an unscoped one that mixes scenarios). One query per dataset. Each result includes the `sql` it ran: copy it into that dataset's `sql` field so the info popover can show how the data was fetched. If a result is long, split it by period range into several queries and keep each result as its own file.
5. **Reconcile query.** Run one more query with **no dimensions** for each headline metric, with the same filters. Its totals go into `reconcile`. This is what proves you copied every row correctly.
6. **Write the files** into a working folder (`./semantic-explorer/<short-name>/`, or `/home/claude/` in a chat environment). For each result write `{"rows": [...]}` copying the tool's `rows` exactly, or the more compact `{"columns": [...], "data": [[...], ...]}`. Values may be rounded to whole numbers. Do not edit, sort or "tidy" values. Then write `spec.json` (format and a worked example in `references/snapshot-format.md`).
7. **Build:**
   ```
   python3 <this skill's folder>/scripts/build_snapshot.py --spec spec.json --out dashboard.html
   ```
   Read the output. It lists the datasets, what reconciled, and **what the dashboard opens with** (each KPI's latest value and change). Compare those numbers with numbers you already got from queries. If it prints `ERROR:` the message says what to fix; fix that and rebuild. Never edit the HTML by hand and never skip a reconcile failure: it means rows were dropped, duplicated or mistyped.
8. **Deliver.** Save the file where the user can open it and say where. In claude.ai or Cowork, put it in the outputs folder and present it (or publish it as an artifact if an artifact tool is available). In Claude Code, give the path and offer to open it. Then in two or three sentences say what is on it and how to use it: filters on top (click a chip to change it, `+ Add filter` to add one), ⓘ for definitions, ✦ to ask you about a tile (it copies a prefilled question to paste into the chat, or sends it directly where the page is shown inline), pencil to edit a tile, Reset edits to go back. Say it is a snapshot as of today and that the file contains the data.
   **Inline ask (optional).** When the dashboard is published as an artifact and the user has a Snowflake connector in claude.ai, set `"ask": {"connector": "<connector display name>", "tool": "ask_semantic_view"}` in the spec and a `view` on every metric. Then publish with `capabilities: {"mcp": {"servers": [{"server": "<same display name>", "tools": ["ask_semantic_view"]}]}}`. The ✦ dialog then gains **Ask Snowflake**: the question goes straight to `ask_semantic_view` on the tile's own view with the viewer's credentials and the answer, rows and SQL appear in the dialog, with no copying. "Ask Claude in chat instead" stays as the fallback, and is the only button anywhere the connector is unavailable (a saved file, another viewer, no connector). Tell the user the first click asks for permission and that the viewer needs a Snowflake role that can see the views. The display name must match the connector exactly; if unsure, ask the user to read it from claude.ai Settings → Connectors.

### Rules the page imposes (read before planning datasets)

1. **One series dataset.** The page fetches every KPI and line-tile metric (and any `compare` metric) in a single combined query by the time dimension, so **one dataset must hold all of them** (for a ratio, both its numerator and denominator). Metrics from different views, or cuts that differ by category, will not load together: the tiles show "Failed to load". For a dashboard that spans several views, build a **wide time-only dataset** (for example `monthly`): one row per period, one column per additive part, each column the sum of the matching detail dataset. Breakdown bars and tables are queried per tile, so they keep their own detail datasets. Consequence: category filters change the bars and tables only, not the KPIs or trends; say so in the subtitle.
2. **Segments over time.** To chart one segment as a trend (a single supplier, MTO versus MTS, one lane), add that segment's numerator and denominator as extra columns of the wide dataset, declare a ratio metric for each, and list them in one tile's `metrics` so the measure selector switches between them.
3. **Time grain.** The time dimension must be sortable text (`2026-03`). If the view only exposes a date, roll the governed daily result up in one statement over the view and weight every ratio by its own denominator, never an average of ratios:
   ```sql
   SELECT TO_CHAR(DATE_TRUNC('month', d),'YYYY-MM') AS month, SUM(den) AS den, ROUND(SUM(rate*den)) AS num
   FROM SEMANTIC_VIEW(<view> DIMENSIONS <table>.<date> AS d METRICS <table>.<RATE> AS rate, <table>.<DEN_METRIC> AS den)
   GROUP BY 1 ORDER BY 1
   ```
   Put that statement in the dataset's `sql`. Reconcile the total against a no-dimension governed query over the same window.
4. **A rate with no additive numerator.** `ROUND(rate * denominator)` at the finest governed grain is the on-time (or late) count; rates carry six decimals, so it is exact for counts. Say in the metric `description` that it is derived. Use a base table only if no governed route exists **and** the concept's own `formula`, run on it, reproduces the governed total exactly; reconcile and say so.
5. **Incomplete latest period.** Before defaulting to the newest period, compare its volume and open items with the previous periods. If it is clearly partial (open PO lines, unconfirmed production, a half-filled month), set the time filter's end to the last complete period (`"filters": [{"dimension": "MONTH", "op": "between", "values": ["2024-10", "2026-08"]}]`), keep the partial period in the data so the user can widen the range, and say so in `subtitle`. The build preview honours this filter, so it should print the same KPI values the page opens with.
6. **Limits to remember.** A dataset `sql` over 4,000 characters is rejected: summarise long statements. Give a table `"span": 12` when it has more than three metrics or it clips. Total the files with a script before building so a missing row is caught before the reconcile check does. Line charts zoom their axis automatically when every value is positive and the range is under half of the maximum; the tick labels always show the scale.

### Changing a dashboard you built

Do not start over. Keep `spec.json` and the data files. Write the changes as operations in `ops.json` and rebuild:

```
python3 <skill>/scripts/build_snapshot.py --spec spec.json --ops ops.json --out dashboard.html
```

Operations: `set_title`, `add_tile`, `update_tile`, `remove_tile`, `move_tile`, `set_filter`, `remove_filter` (shapes in `references/snapshot-format.md`). Edits are saved back into `spec.json`. When the user wants a cut the file does not contain (another dimension, a longer period), add a dataset or extend one, reconcile it, and rebuild. Tell the user their browser-side tile edits in the old file are not carried into the new one.

### When the user clicks ✦ "Explain this data"

You will receive a question followed by a block starting `Dashboard context`. Treat the metric and dimension names as exact, the active filters as scope, and the figures as already known. Do not just restate them.

0. If the page was published with inline ask, the dialog's **Ask Snowflake** button already did this step for the viewer; a message that reaches you in chat came from "Ask Claude in chat instead" or a page without it.
1. **Always start with `ask_semantic_view`**, on the view that owns the tile's metric (when the dashboard spans several views, take the view from the dataset or metric the tile uses, not from the page title). Send the user's question as written, with the active filter values added in plain words and `AGG(metric)` for the measure. Do this even when an agent tool such as `agent_run` exists; use that only when the user asks for it by name or the question cannot be answered inside one view after step 1. Say in one sentence which tool you used.
2. **Read what it says it could not do.** If it reports that a requested cut is not related to the metric (for example lanes and customer order lines), say so plainly, do not invent a mapping, and offer the nearest stand-in cut, labelled as a stand-in.
3. Where the ontology has the concept, follow its relationships to related concepts and query their bound views (same domain, at most three hops), or use the `deep-dive` skill for a long "why".
4. **Confirm every figure you quote with `query_semantic_view`.** Compute any contribution split yourself from the confirmed figures (rate effect at the earlier period's weights, plus mix effect) instead of repeating the model's arithmetic.
5. **Show it.** Draw the decomposition or trend (see "Showing results" in the `analyze-domain` skill) before the prose.
6. Say which filters your answer assumes, name the path you followed, and offer to add the finding to the dashboard as a note or a new tile.

## Path C: quick look

For one or two numbers or one chart, answer inline with a small chart and a sentence, using the host's chart tool (see "Showing results" in `analyze-domain`). Offer a full dashboard only if the user is exploring.

## Honest limits (say them when relevant, briefly)

- A snapshot is a copy as of the build time; ask you to rebuild for fresh numbers.
- It holds what you queried. A filter on a field that a tile's data lacks is not applied there, and the tile says so.
- The file contains data. It is as sensitive as the data in it.
- Browser-side tile edits live in that browser only.

## Files in this skill

- `scripts/build_snapshot.py`: validates, reconciles, applies edits, writes the HTML. Python 3.9+, standard library only.
- `assets/explorer.template.html`: the page (generated from the shared UI source; do not edit).
- `references/snapshot-format.md`: spec and data file formats, operations, every error and its fix.
- `references/control-mapping.md`: how to choose KPIs, charts and filters from the view's metadata.
