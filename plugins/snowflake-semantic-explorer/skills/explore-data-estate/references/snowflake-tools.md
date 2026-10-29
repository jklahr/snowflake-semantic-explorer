# The Snowflake MCP tools: what they do and how to call them

Tool names and arguments below are the ones on the reference server. If yours differ, use the nearest equivalent (table at the end). Look at the tool list before assuming.

## The tools

| Tool | Use it to | Notes |
|---|---|---|
| `business_ontology` | find what a business concept **means** and which data objects implement it | see "The ontology" below |
| `list_semantic_views` | list semantic views, optionally within one database and schema | big accounts have many; filter before showing anything |
| `describe_semantic_view` | get the **metrics and dimensions** of one view | these names are the only ones you may request later |
| `query_semantic_view` | run one certified query and get the rows plus the statement it ran | **never pass SQL** |
| `ask_semantic_view` | answer one plain-language question against one view | for investigation, not for the numbers you will publish |
| SQL tool (`sql_exec_tool` or similar) | last resort only: read-only SQL when no governed tool can answer | say so when you use it |
| an agent tool (Cortex Agent run) | long, multi-step investigations | see the `deep-dive` skill |

## `query_semantic_view`: argument conventions

The list-valued arguments are **JSON strings, not arrays**. The connector rejects a real array. An argument you do not need is the string `[]`.

| Argument | Form | Example |
|---|---|---|
| `METRICS` | string containing a JSON list of metric names | `"[\"ACTUAL_NET_REVENUE\"]"` |
| `DIMENSIONS` | string containing a JSON list | `"[\"FISCAL_PERIOD\",\"BRAND\"]"` or `"[]"` for a total |
| `FILTERS` | string containing a JSON list of `{dimension, op, values}` | `"[{\"dimension\":\"FISCAL_YEAR\",\"op\":\"=\",\"values\":[\"2026\"]}]"` |
| `HAVING_FILTERS` | same, applied to metric values after grouping | `"[]"` when unused |
| `ORDER_BY` | string containing a JSON list of `{name, direction}` | `"[{\"name\":\"ACTUAL_NET_REVENUE\",\"direction\":\"DESC\"}]"` |
| `ROW_LIMIT`, `DB_NAME`, `SCHEMA_NAME`, `VIEW_NAME` | plain values | `ROW_LIMIT` 1000 |

- `DB_NAME` and `SCHEMA_NAME` are the view's database and schema; `VIEW_NAME` is its name.
- Filter operators seen to work: `=`, `>=`, `<=`, `LIKE` (use `%`). Compare strings such as fiscal periods with `>=` / `<=`.
- To change the cut (another dimension, a filter), call again with **one argument changed**. Do not write the statement yourself.
- The result has `rows` (objects keyed by the names you asked for, upper case) and `sql` (the statement). Keep `sql`; it is the proof the number came from governed metrics.
- Scenario trap: use explicitly scoped metrics (`ACTUAL_...`, `BUDGET_...`). An unscoped metric may add scenarios together.
- Periods with plan but no actuals come back with `0` actuals. They are not "zero revenue".

## `ask_semantic_view`

Pass the view and one clear question. Prefer a **defined metric**, written `AGG(metric)` in your wording ("what is AGG(ACTUAL_NET_REVENUE) by brand for FY2026?"). Fall back to the tables under the view only when no metric can answer, and say so. Use it to explore or explain; re-run the figures you will quote through `query_semantic_view`.

## The ontology (`business_ontology`)

The ontology says what a concept means and where its data lives. A semantic view then produces the number. Do not assume a domain, a table or a view; discover them.

1. **Domains.** Call with `DOMAIN_NAME` and `QUERY` both empty. It returns the domains this caller can read, each with a term count and a breakdown by kind. Show them to the user and ask which to use. Also offer "no ontology, semantic views only". If the user already named the domain, use it and confirm it in your answer.
2. **Concepts.** Call with the chosen `DOMAIN_NAME` and a short `QUERY` (a term, not a sentence). One search returns **several** concepts of different kinds (`METRIC`, `ENTITY`, `POLICY_CONCEPT`, `TERM`, ...). Keep the one whose name, synonym or description fits the question (prefer an ACTIVE metric). The reply also repeats the domain list; ignore it.
3. **Search only the chosen domain.** If a result comes from another domain, discard it and say so. When a name exists in more than one domain, pass the domain so the right one resolves.
4. **Read the concept.**
   - `description` is the governed definition; `formula` appears for metrics and states the grain (`... GROUP BY fiscal period, customer, product`); `synonyms` help matching.
   - `assets` say where the data lives. **Prefer an asset whose `objectType` is `Semantic View`.** `fqn` is the view, `subObjectName` is the **metric name in that view**, `entityQualifier` is its logical table. Use a table, view or column only when no semantic view is bound, and say why.
   - `relationships` has `edges` and `nodes`. **Edges refer to terms by id** (`sourceTermId`, `targetTermId`); resolve the names through `relationships.nodes`. `truncated: true` means there are more edges than were returned.
5. **Read edges like this.** An edge is "source *type* target". `direction` is relative to the concept you asked about (`UPSTREAM` = it points at you, `DOWNSTREAM` = you point at it).

   | `relationshipType` | Meaning |
   |---|---|
   | `DERIVES` | **source DERIVES target means the target is computed from the source.** Gross Sales DERIVES Net Revenue: Net Revenue is built from Gross Sales. For "what drives X", take the edges where X is the target |
   | `MEASURES` | the metric measures an entity (Product, Customer): the grain you can slice by |
   | `HAS_VARIANT` | a scenario or version of the same concept (Net Revenue has Planned Net Revenue and Latest Estimate Net Revenue). Use it to find the plan and forecast twins of a metric |
   | `APPLIES_TO` | a **policy** that governs a metric (see below) |
   | `SCOPES` | a dimension or term that scopes a metric (for example Scenario) |
   | `CUSTOM` | read the `label`: "reduces", "distinct from", ... "reduces" is also a driver; "distinct from" is a warning not to confuse two concepts |

6. **Read the policy concepts that apply.** A `POLICY_CONCEPT` is a rule. Examples seen: "Actual Scenario Default" (when scenario is not stated, use Actual), "Latest Estimate Is FY2026 Only", "Like-for-Like YTD", "Cross-View Reconciliation" (net revenue must match between two views; a mismatch means a filter or scenario error). Follow `APPLIES_TO` edges to the policies on your concept, apply them and say that you did. Use a reconciliation policy as a check on your own result.
7. **Check the bound metric is the one you want.** The metric an asset names can be **unscoped across scenarios**. For example the concept "Net Revenue" is bound to `PNL_NET_REVENUE`, which sums Actual, Budget and Latest Estimate together, while `ACTUAL_NET_REVENUE` is the Actual-only twin. Either filter the scenario dimension to the scenario the policies call for (usually Actual), or use the scoped twin, and say which you did and why. Never present an unscoped total as the actual figure.

## When a tool is missing or fails

| Need | If the dedicated tool is missing or fails | Notes |
|---|---|---|
| list views | SQL tool: `SHOW SEMANTIC VIEWS IN ACCOUNT` | |
| describe a view | SQL tool: `DESCRIBE SEMANTIC VIEW <db>.<schema>.<view>` | rows are `object_kind`, `object_name`, `parent_entity`, `property`, `property_value`. Kinds: METRIC, DIMENSION, FACT, TABLE. Properties include `COMMENT` (the description), `EXPRESSION`, `DATA_TYPE`, `SYNONYMS`, `SAMPLE_VALUES`. Retry the dedicated tool once first: it sometimes fails with `Unknown user-defined function ...DESCRIBE_SEMANTIC_VIEW` and then works or not; the SQL form worked when it did not. |
| governed query | SQL tool: `SELECT * FROM SEMANTIC_VIEW(<view> DIMENSIONS <table>.<dim> METRICS <table>.<metric> WHERE <cond>)` | qualify names with the logical table in `parent_entity` |
| natural-language question | the server's Cortex Analyst tool pointed at the view | |
| business glossary | none: skip it; use `COMMENT` properties and say definitions come from the view | |

## Reading a metric's `EXPRESSION`

`DESCRIBE` shows how each metric is built. `SUM(x)` is **additive**: it can be summed over any grouping or filter. `SUM(a) / NULLIF(SUM(b), 0)` is a **ratio of two additive metrics**: find the metrics whose expressions are `SUM(a)` and `SUM(b)` (for example `ACTUAL_GROSS_MARGIN_PCT` is `ACTUAL_GROSS_PROFIT` over `ACTUAL_NET_REVENUE`). Never add ratios up; recompute them from their parts. A distinct count or anything else is not safe to re-aggregate.

## Rules that hold for every server

- Use only metric and dimension names the server returned. Never invent them.
- Prefer governed metrics over hand-written aggregates.
- If a SQL form is rejected, read the error and adjust once. Say what you tried if you give up.
- Empty or truncated is not "no data": check the row limit and the filters.
- The session runs as the signed-in user. Do not try to switch roles.
