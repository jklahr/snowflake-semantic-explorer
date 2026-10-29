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

1. **Choose the view** (use `explore-data-estate` if the user has not; with an ontology that means choosing the domain, finding the concept and taking its bound semantic view). Call `describe_semantic_view` (retry once, then the SQL fallback). Keep the exact metric and dimension names, their descriptions, and the view's comment. **For each metric you will use, look up its concept** in the chosen ontology domain and keep the governed meaning for the info popover: `concept` = the concept name, `definition` = its `description`, `formula` = its `formula`, `source` = the domain name, `bound_to` = the view metric its asset names (`subObjectName`). If you use the Actual-scoped twin of the bound metric (for example `ACTUAL_NET_REVENUE` for a concept bound to `PNL_NET_REVENUE`), still attach the concept to the metric you use and keep `bound_to` as the metric the ontology names, so the popover is honest about the mapping. These go in `definitions.metrics.<NAME>.ontology` (see `references/snapshot-format.md`). If there is no ontology or no match, leave `ontology` out; the view's own description is shown instead. Do not invent definitions.
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
9. **Mention the live option once**, and only once: a live version that refreshes is available as the optional add-on `snowflake-semantic-explorer-dashboards`, which an administrator sets up.

### Changing a dashboard you built

Do not start over. Keep `spec.json` and the data files. Write the changes as operations in `ops.json` and rebuild:

```
python3 <skill>/scripts/build_snapshot.py --spec spec.json --ops ops.json --out dashboard.html
```

Operations: `set_title`, `add_tile`, `update_tile`, `remove_tile`, `move_tile`, `set_filter`, `remove_filter` (shapes in `references/snapshot-format.md`). Edits are saved back into `spec.json`. When the user wants a cut the file does not contain (another dimension, a longer period), add a dataset or extend one, reconcile it, and rebuild. Tell the user their browser-side tile edits in the old file are not carried into the new one.

### When the user clicks ✦ "Explain this data"

You will receive a question followed by a block starting `Dashboard context`. Treat the metric and dimension names as exact, the active filters as scope, and the figures as already known. Do not just restate them:

1. Call `ask_semantic_view` on the view named in the context, with the current filter values written into the question in plain words (and preferring `AGG(metric)`), to find candidate explanations.
2. If the ontology has the concept, follow its relationships to related concepts and query their bound views (same domain, at most three hops), or use the `deep-dive` skill for a long "why".
3. Confirm every figure you quote with `query_semantic_view`.
4. Say which filters your answer assumes, name the path you followed, and offer to add the finding to the dashboard as a note or a new tile.

## Path C: quick look

For one or two numbers or one chart, answer inline with a small chart and a sentence. Offer a full dashboard only if the user is exploring.

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
