# Snapshot format

Three kinds of file: **data files** (query results), **`spec.json`**, and optionally **`ops.json`** for edits. Everything is plain JSON.

## Data files

Either of these shapes, or a bare list of row objects:

```json
{"rows": [{"FISCAL_PERIOD": "FY2026-P01", "BRAND": "Ridgeline", "ACTUAL_NET_REVENUE": 8499905.29}]}
```
```json
{"columns": ["FISCAL_PERIOD", "BRAND", "ACTUAL_NET_REVENUE"], "data": [["FY2026-P01", "Ridgeline", 8499905.29]]}
```

- Column names match case-insensitively. Extra columns are ignored.
- Metric values may be numbers or numeric strings (`"1,234.50"`). `null` is allowed and ignored in sums. Dimension values may be anything; blanks become `(blank)`.
- The same dataset can have several files (chunks); they are concatenated. A dimension combination may appear only once across all chunks.

## spec.json

```json
{
  "title": "Expedition Foods P&L",
  "subtitle": "optional",
  "view": "SEMANTIC_SKILLS.EXPEDITION_DEMO.EXPEDITION_PROFIT_AND_LOSS",
  "view_comment": "optional text from the view",
  "exported_by": "optional, shown in the footer",

  "catalog": {
    "metrics": [
      {"name": "ACTUAL_NET_REVENUE", "label": "Net revenue", "format": "currency", "description": "Gross sales less trade spend."},
      {"name": "BUDGET_NET_REVENUE", "label": "Budget net revenue", "format": "currency"},
      {"name": "ACTUAL_GROSS_PROFIT", "label": "Gross profit", "format": "currency"},
      {"name": "GROSS_MARGIN_PCT", "label": "Gross margin %", "format": "percent", "num": "ACTUAL_GROSS_PROFIT", "den": "ACTUAL_NET_REVENUE"}
    ],
    "dimensions": [
      {"name": "FISCAL_PERIOD", "label": "Fiscal period", "type": "time"},
      {"name": "BRAND", "label": "Brand"}
    ]
  },

  "definitions": {"metrics": {"ACTUAL_NET_REVENUE": {"ontology": {"concept": "Net revenue", "source": "Finance (ontology domain)", "definition": "the concept's description", "formula": "optional formula from the concept", "bound_to": "optional: the view metric the ontology names"}}}},

  "datasets": [
    {"id": "by_period_brand", "dimensions": ["FISCAL_PERIOD", "BRAND"],
     "metrics": ["ACTUAL_NET_REVENUE", "BUDGET_NET_REVENUE", "ACTUAL_GROSS_PROFIT"], "files": ["period_brand_1.json", "period_brand_2.json"]},
    {"id": "top_customers", "dimensions": ["CUSTOMER_NAME"], "metrics": ["ACTUAL_NET_REVENUE", "ACTUAL_GROSS_PROFIT"],
     "files": ["customers.json"], "partial": true, "note": "Top 25 customers by net revenue.",
     "sql": "the statement query_semantic_view returned for this result (optional, shown in the info popover)"}
  ],

  "trim_after_last_actual": "ACTUAL_NET_REVENUE",
  "reconcile": [{"dataset": "by_period_brand", "metric": "ACTUAL_NET_REVENUE", "total": 881500772.0}],

  "tiles": [], "filters": [], "auto": {"metrics": [], "pop": "MoM", "kpis": 4}
}
```

**Required:** `title`, `view`, `catalog`, `datasets`. Everything else is optional.

- **catalog.metrics**: `format` is `currency`, `percent` or `number`. `lower_is_better: true` colors an increase red (costs, churn). A ratio has `num` and `den`, both metrics in the catalog; ratios are **not** listed in a dataset's `metrics`; the page computes them from the numerator and denominator wherever both are present.
- **catalog.metrics[].view** (optional, required when `ask` is set): the fully qualified `DATABASE.SCHEMA.VIEW` that owns the metric. For a ratio, the view that owns its parts. Used by the inline ask to pick the right view per tile.
- **ask** (optional, top level): `{"connector": "<connector display name>", "tool": "ask_semantic_view", "view": "<default fully qualified view>"}`. Enables **Ask Snowflake** in the ✦ dialog on a page published with the matching `mcp` capability; harmless elsewhere.
- **catalog.dimensions**: `type` is `time` for exactly one dimension (its values must sort correctly as text: `FY2026-P01`, `2026-03`, `2026-03-15`, `2026Q1`). The grain and periods per year are detected from the values; override with `"time": {"dimension": "...", "grain": "month", "periods_per_year": 12}`.
- **definitions**: shown in the ⓘ popover. `ontology` comes from the business ontology concept (`concept`, `definition` = its description, `source` = the domain, optional `formula` and `bound_to`). Anything not given is filled from the catalog descriptions.
- **datasets**: `sql` is the statement the query tool returned (at most 4,000 characters). A dataset lists the dimensions it is grouped by and the (additive) metrics it holds. `partial: true` marks a top-N table that does not cover everything; it can only answer at its own grain and is never used for totals.
- **trim_after_last_actual**: name of an actual metric. Periods after the last period where it is non-zero are removed, so plan-only future periods do not skew comparisons.
- **reconcile**: for each headline metric, the total from an independent no-dimension query. Optional `"where": {"BRAND": "Ridgeline"}` for a slice. The build **fails** if the dataset's sum differs by more than rounding.
- **tiles / filters / auto**: omit `tiles` to get defaults (4 KPIs with sparkline and period-over-period change and a budget comparison where a `BUDGET_`/`PLAN_`/`TARGET_` twin exists, a trend line, a breakdown bar chart, a detail table; filters for the time dimension and the first two category dimensions). `auto` tunes the defaults. To specify tiles yourself:

```json
{"type": "kpi",  "title": "Net revenue", "metric": "ACTUAL_NET_REVENUE", "pop": "MoM", "sparkline": true, "value_mode": "latest",
 "compare": {"metric": "BUDGET_NET_REVENUE", "label": "vs budget"}, "span": 3}
{"type": "line", "title": "Trend", "metrics": ["ACTUAL_NET_REVENUE"], "x": "FISCAL_PERIOD", "compare": "BUDGET_NET_REVENUE", "span": 8}
{"type": "hbar", "title": "By brand", "metrics": ["ACTUAL_NET_REVENUE", "ACTUAL_GROSS_PROFIT"], "x": "BRAND", "limit": 15, "span": 4}
{"type": "bar",  "title": "...", "metrics": ["..."], "x": "DIM", "limit": 12}
{"type": "table", "title": "Customers", "metrics": ["..."], "groupBy": "CUSTOMER_NAME", "limit": 25, "span": 12}
```
`pop` is one of `none`, `DoD`, `WoW`, `MoM`, `QoQ`, `YoY`. `value_mode` is `latest` (the latest period with data) or `total` (over the selected range). `span` is the width out of 12. A tile with more than one metric gets a measure selector.

Filters: `{"dimension": "BRAND", "op": "in", "values": []}` (empty list means All). Operators: `in`, `not_in`, `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `between` (two values, `null` for open), `contains`, `starts_with`.

## ops.json (edits)

A list, applied in order, all or nothing:

```json
[
  {"op": "set_title", "title": "New title"},
  {"op": "add_tile", "tile": {"type": "hbar", "title": "CM by brand", "metrics": ["ACTUAL_CONTRIBUTION_MARGIN"], "x": "BRAND"}, "index": 2},
  {"op": "update_tile", "id": "t1", "changes": {"pop": "YoY", "sparkline": false, "compare": null}},
  {"op": "remove_tile", "id": "t4"},
  {"op": "move_tile", "id": "t2", "index": 0},
  {"op": "set_filter", "filter": {"dimension": "BRAND", "op": "in", "values": ["Ridgeline"]}},
  {"op": "remove_filter", "dimension": "CUSTOMER_NAME"}
]
```
In `changes`, `null` removes a field. Edits are written back into `spec.json`.

## Errors and fixes

| Message contains | Cause and fix |
|---|---|
| `is not valid JSON` | a file was truncated or has a stray character; rewrite it |
| `missing columns` | the query did not return a column the dataset declares; re-query or fix `dimensions`/`metrics` |
| `share the same ... chunk was included twice` | duplicate rows: a file listed twice, or the query grouped by fewer dimensions than declared |
| `has N values but M columns` | a row in a `columns`/`data` file is ragged; recopy |
| `is not a number` | a metric value is text; copy the number as returned |
| `sums to X ... but the independent query says Y` | rows dropped, duplicated or mistyped; recopy the results exactly and rebuild. Never loosen the check |
| `ratio ... Put its numerator` | a ratio metric was listed in a dataset; list the numerator and denominator instead |
| `no dataset provides that` | a tile needs a cut no dataset has; add a dataset, or change or remove the tile |
| `no complete dataset has them` | a total was asked of a top-N (partial) table; add a complete dataset |
| `ask must be an object` / `ask is set, so every metric needs a 'view'` / `view must be a fully qualified` | add `ask.connector`, and a three-part `view` on every non-ratio metric (or set `ask.view` as a default) |
| `more than the ... limit` | too many rows; shorten the period window or drop a dimension |
