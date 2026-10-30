---
name: explore-data-estate
description: Navigate and map a Snowflake data estate: which business domains exist, which concepts they define, and which semantic views hold the numbers. Use whenever the user asks what data is available, which semantic view to use, what a domain or term means, "what can I analyze", or names a business area (sales, revenue, cost, supply chain, customers) without saying which view holds it. Also use at the start of any dashboard or analysis request when the view has not been chosen yet, even if the user does not say "explore".
---

# Explore the data estate

snowflake-semantic-explorer v0.6.0

> Tool names, argument formats and fallbacks are in `references/snowflake-tools.md`. Read it before the first tool call.

Accounts often hold dozens to hundreds of semantic views, many of them demos, copies or superseded versions. The goal is to get the user from "what do we have?" to one well-understood view quickly, **starting from business meaning rather than from a list of tables**, without dumping a giant list on them.

## Workflow

1. **If there is a business ontology, start there.** Call `business_ontology` with an empty domain and empty query. It returns the domains with a term count. Show them and ask the user which to use; also offer "no ontology, use semantic views only". If they already named a domain or a term, use it and say so. Search **only** the chosen domain; discard results from other domains and say you did.
2. **Find the concept.** Search the chosen domain with a short term. Keep the match that fits (prefer an ACTIVE metric). Read its definition, formula, relationships and `assets`. Prefer the asset whose type is `Semantic View`: that view is your answer to "where do the numbers live". Note any concept that has no data bound to it.
3. **If there is no ontology, or the concept has no view, list views.** Call `list_semantic_views` at most once and filter it yourself. Use the ontology domain and concept names as keywords against view names and comments. Do not print the list. Show at most 5 to 8 candidates. If a concept's semantic-view asset has `fqn` null, match comments the same way. If the domain has bound assets but no visible view, stop and report a grants or visibility gap. Do not substitute another view.
4. **Read the comments as guidance.** View comments often say "START HERE", "superseded by X", "excludes internal accounts", "actuals run through period N". Prefer the non-legacy, non-test view and say why you skipped others.
5. **Describe only the view that matches the question.** Call `describe_semantic_view` for that view. If a domain has several views, give each other view a one-line purpose and mark it "available, not yet described". If describe fails, retry once, then use the SQL fallback in the tools reference.
6. **Summarize the chosen view in a compact card:** what it is for (with the governed definition if the ontology has one), grain, time coverage, 4 to 6 headline metrics, key dimensions, and caveats. When comparing several views, a compact table is enough; no chart is required.
7. **Offer next steps.** If the next message asks for numbers, load `analyze-domain`. If it asks why, also load `deep-dive`. If the views and ontology do not cover the question, call `list_governed_catalog` once. Offer Cortex Sense only when `senses` is not empty, and only after the user agrees. A Sense result must cite the sense, the document or table, and the definition or SQL, and must say it is exploratory.

## Output style

Lead with a recommendation ("For revenue questions use X; Y is a legacy version"). Use a short table only when comparing several views. Do not paste raw metadata; translate names into plain language and keep the exact metric and dimension identifiers for later steps.

## Pitfalls

- Do not assume a domain, table or view. Discover them.
- Do not invent metric or dimension names; only names `describe_semantic_view` returned are valid.
- Do not assume two views with similar names are equivalent; check comments and metrics.
- Cross-domain questions usually need a view that was built for both. Do not join two views by guesswork; join only where the ontology has a relationship between their concepts.
