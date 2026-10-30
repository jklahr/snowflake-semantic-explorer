# Changelog

## 0.5.0

- List semantic views, ontology domains, and Cortex Sense contexts with `list_governed_catalog` before choosing what an agent run may use.
- Add `ask_governed` run types: semantic views only, views plus ontology, and views plus ontology plus Cortex Sense.
- Default numbers stay on `query_semantic_view`. Domain discovery and root cause use the ontology.
- Offer Cortex Sense only when the curated views and ontology cannot answer, and only after the user agrees. A Sense result is exploratory: cite the sense, the document or table, and the definition or SQL.

## 0.4.0

- Show the right visual for a result: the host chart for a simple series, the host visual tool for contribution and mixed-unit charts, a table for exact values, and a dashboard when the user will explore the result.
- Ask a semantic view first. A free-text question or an "Explain this data" message calls `ask_semantic_view` on the view that owns the metric, then confirms quoted figures with `query_semantic_view`.
- Use an agent run only for long, multi-step work, or when the user asks for an agent. If that tool is absent, say so instead of substituting it silently.
- Draw the decomposition before the prose, label mix separately from rate, and do not exaggerate a change by truncating an axis.
- Let a snapshot answer inside the page when it is published with the viewer's connector. Saved files and the live dashboard keep the chat route. A line chart zooms only when every value is positive and the range is under half the maximum.
- Validate that every dashboard metric names its semantic view, and make the snapshot preview honor the default end date.
- Remove the optional live-dashboard add-on from the marketplace. Snapshot dashboards remain in the core plugin.
