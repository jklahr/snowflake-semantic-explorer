---
name: explore-data-estate
description: Navigate and map a Snowflake data estate: which business domains exist, which concepts they define, and which semantic views hold the numbers. Use whenever the user asks what data is available, which semantic view to use, what a domain or term means, "what can I analyze", or names a business area (sales, revenue, cost, supply chain, customers) without saying which view holds it. Also use at the start of any dashboard or analysis request when the view has not been chosen yet, even if the user does not say "explore".
---

# Explore the data estate

> Tool names, argument formats and fallbacks are in `references/snowflake-tools.md`. Read it before the first tool call.

Accounts often hold dozens to hundreds of semantic views, many of them demos, copies or superseded versions. The goal is to get the user from "what do we have?" to one well-understood view quickly, **starting from business meaning rather than from a list of tables**, without dumping a giant list on them.

## Workflow

1. **If there is a business ontology, start there.** Call `business_ontology` with an empty domain and empty query. It returns the domains with a term count. Show them and ask the user which to use; also offer "no ontology, use semantic views only". If they already named a domain or a term, use it and say so. Search **only** the chosen domain; discard results from other domains and say you did.
2. **Find the concept.** Search the chosen domain with a short term. Keep the match that fits (prefer an ACTIVE metric). Read its definition, formula, relationships and `assets`. Prefer the asset whose type is `Semantic View`: that view is your answer to "where do the numbers live". Note any concept that has no data bound to it.
3. **If there is no ontology (or the concept has no view), list views.** Call `list_semantic_views` and filter it yourself using the user's topic against view names and comments. Show at most 5 to 8 candidates.
4. **Read the comments as guidance.** View comments often say "START HERE", "superseded by X", "excludes internal accounts", "actuals run through period N". Prefer the non-legacy, non-test view and say why you skipped others.
5. **Describe the shortlisted view(s)** with `describe_semantic_view` to get metrics and dimensions. If it fails, retry once, then use the SQL fallback in the tools reference and tell the user the metadata call failed.
6. **Summarize each candidate in a compact card:** what it is for (with the governed definition if the ontology has one), grain, time coverage, 4 to 6 headline metrics, key dimensions, and caveats (scenario splits, internal accounts, currency not converted).
7. **Offer next steps** that match what you found: analyze a domain, build a dashboard, or follow a relationship to a related domain. If the user asks something the views and ontology do not cover, call `list_governed_catalog` and show the senses, then ask: "Do you want me to use Cortex Sense to look further? Those results are not certified or curated. They search a broader set of data." Do not call `ask_governed` with `sv_ontology_sense` until they say yes. Any result from that run must cite the sense, the document or table, and the definition or SQL, and must say it is exploratory.

## Output style

Lead with a recommendation ("For revenue questions use X; Y is a legacy version"). Use a short table only when comparing several views. Do not paste raw metadata; translate names into plain language and keep the exact metric and dimension identifiers for later steps.

## Pitfalls

- Do not assume a domain, table or view. Discover them.
- Do not invent metric or dimension names; only names `describe_semantic_view` returned are valid.
- Do not assume two views with similar names are equivalent; check comments and metrics.
- Cross-domain questions usually need a view that was built for both. Do not join two views by guesswork; join only where the ontology has a relationship between their concepts.
