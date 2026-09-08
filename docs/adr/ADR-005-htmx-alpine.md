# ADR-005: HTMX + Alpine.js for Interactivity

## Status

Accepted

## Context

Given the server-rendered UI decision (ADR-004), EMS still needs interactivity common to enterprise applications: search-as-you-type, inline editing, modals, tabbed views, and multi-step forms — without introducing a full SPA framework or duplicating business logic on the client.

## Decision

EMS will use two complementary, narrowly-scoped libraries:

- **HTMX** for server-driven partial page updates: search, filters, pagination, inline forms, and modals loaded on demand. Any interaction that touches data or a business rule goes through HTMX back to Django.
- **Alpine.js**, used strictly for local, client-only UI state that never needs to touch the server or duplicate a business rule — dropdown/modal open-close state, tab switching, and tracking the current step of a multi-step form wizard.

The boundary is deliberate: if an interaction needs to know or affect anything about business data, it is HTMX (server round-trip); if it is purely presentational UI state, it is Alpine.

## Alternatives Considered

- **Stimulus** — rejected. Smaller ecosystem and community for this use case than Alpine, with no compelling advantage to offset that.
- **Vanilla JavaScript only** — rejected. This reinvents patterns HTMX and Alpine already solve cleanly, resulting in more boilerplate and inconsistent patterns across the codebase.
- **A heavier framework (e.g., Vue) used only for "islands"** — rejected. Inconsistent with the server-rendered decision in ADR-004; introduces an unnecessary second UI paradigm for marginal benefit.

## Consequences

**Positive:**
- Minimal JavaScript to write and maintain — both libraries are added via a single `<script>` tag, with no client-side build step required for the majority of interactivity.
- Business logic stays server-side by construction: because HTMX always round-trips to Django for anything that matters, there is no natural place for business rules to leak into the client.

**Negative / Tradeoffs:**
- Some interaction patterns — for example, a rich drag-and-drop scheduler, should attendance or training scheduling ever need one — are more awkward to build in HTMX + Alpine than in a proper SPA framework. This is mitigated case-by-case with a small, targeted library (e.g., SortableJS) for that specific interaction, rather than abandoning the overall server-rendered approach.
