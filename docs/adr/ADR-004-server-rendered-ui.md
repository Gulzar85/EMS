# ADR-004: Server-Rendered UI

## Status

Accepted

## Context

EMS is a data-heavy enterprise HR tool used primarily by HR staff, operations staff, and management on desktop devices, with a secondary use case of employee self-service. We need to choose a UI architecture that fits this usage pattern, fits the team's capacity (see ADR-001), and avoids duplicating business logic between a frontend and a backend.

## Decision

EMS will use **server-rendered Django templates as the sole UI layer**. There is no single-page application (SPA) framework and no separate frontend build pipeline. All pages are rendered by Django views, with interactivity layered on via HTMX and Alpine.js (see ADR-005).

## Alternatives Considered

- **React/Vue SPA with a Django REST API backend** — rejected. This roughly doubles the surface area to build and maintain: a full API layer, a separate frontend application, its own build pipeline, and a client-side state-management layer, none of which is driven by a demonstrated requirement. It also creates strong pressure to duplicate validation and business rules between the frontend and backend — exactly the failure mode the architecture brief warns against.
- **A hybrid model (server-rendered shell with SPA "islands")** — rejected for this phase. It introduces two UI paradigms and the associated cognitive and tooling overhead for marginal benefit over HTMX + Alpine. This can be revisited later, but only if a specific screen proves to need genuinely rich client-side state that HTMX + Alpine cannot reasonably express.

## Consequences

**Positive:**
- Single source of truth for business logic and validation — it lives in Django/Python only, never duplicated on a client.
- Faster initial build: there is no separate API layer and frontend application to design, version, and stand up in parallel.
- Simpler authentication and session model — standard Django sessions, no token issuance/refresh or CORS configuration to manage.
- A natural fit for HTMX's partial-page-update model, keeping pages fast and interactions server-driven.

**Negative / Tradeoffs:**
- This approach is less suited to a future rich, offline-capable mobile application. If that ever becomes a genuine business requirement, it becomes the trigger for introducing a proper API layer on top of the existing service/selector layer — a discussion carried in `../architecture/application-architecture.md`'s API-strategy section, not solved by this ADR.
