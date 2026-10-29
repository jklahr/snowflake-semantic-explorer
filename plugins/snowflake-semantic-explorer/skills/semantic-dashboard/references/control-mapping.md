# From semantic view metadata to dashboard controls

The semantic view tells you what is measurable and how it can be sliced. Let that drive the layout rather than guessing.

## Metrics -> components

| Metadata signal | Component |
|---|---|
| The headline measure of the domain (revenue, cost, orders) | First KPI card, with a `compare` to its budget, plan or prior-period counterpart if one exists |
| A scoped pair such as `ACTUAL_X` and `BUDGET_X` | KPI `compare`, and a line chart with `compare` |
| Several related additive measures (revenue, gross profit, margin $) | One chart with a measure selector (`metrics` list) |
| A rate, share or margin | Ratio metric built from additive parts; KPI card and measure-selector option |
| Count of entities | KPI card; avoid summing across periods when it counts distinct things (check the description) |
| Anything the description calls "snapshot", "balance", "latest" or "distinct" | Not safe to sum over time; show latest period only, or leave out |

Keep to 4 KPI cards. Order them from outcome to driver (revenue before volume). Put the unit in the format, not the label.

## Dimensions -> components

| Metadata signal | Component |
|---|---|
| Time dimension (date, month, fiscal period) | Line chart x-axis and the From/To range |
| Low-cardinality category (under about 15 values: brand, region, segment, channel) | Filter dropdown and a `hbar` breakdown |
| Medium-cardinality category (15 to 100: customer, product) | Table `groupBy` with a `limit`; not a filter unless asked |
| High-cardinality or identifier dimension (order id, user) | Do not include |
| Hierarchies (country > region > city) | Filter on the top level; breakdown at the level the story needs |

## Layout rules

1. Title, then a takeaway sentence with the headline number and the biggest deviation.
2. Filters bar.
3. KPI cards (2 to 4).
4. One time-series chart, then one breakdown chart.
5. Detail table last.

## Choosing what to build

If the user gave no instructions, pick the domain's headline metric, one budget or prior comparison, one margin or rate, the main time dimension and the one or two category dimensions with the most variation. Then offer to add more rather than starting wide.

## Traps seen in practice

- Metrics that are not scoped by scenario sum Actual, Budget and Forecast together. Use scoped metrics, or filter the scenario dimension, and say which.
- Future periods often return zeros for actual metrics. Exclude them so lines do not collapse to zero.
- A budget comparison is only meaningful over periods where actuals exist. Budget rows for future periods have nonzero budget and zero actuals, which would make every KPI look badly under plan. Drop those periods entirely (both actual and budget) before building the spec.
- Currency may not be converted; check the metric description before labelling values "USD".
