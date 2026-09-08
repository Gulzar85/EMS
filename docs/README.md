# EMS — Phase 00 Architecture & Engineering Specification

Enterprise Employee Management System for McDonald's Pakistan. This package is the complete Phase 00 deliverable: architecture, database, security, frontend, and development specifications for a Django modular monolith. **No application code, models, or migrations exist yet** — this is the design a Django team executes against in Phase 01.

## How to read this package

Start with `architecture/system-architecture.md` for the big picture, then `architecture/django-app-map.md` for how the 18 Django apps divide responsibility. The `adr/` folder explains *why* each major call was made — read those before challenging a decision elsewhere in the docs.

## Architecture

- [System Architecture](architecture/system-architecture.md) — actors, external systems, NFRs, data privacy categories
- [Application Architecture](architecture/application-architecture.md) — layering (View → Service → Selector → ORM), request lifecycle
- [Domain Architecture](architecture/domain-architecture.md) — the 17 business domains, employee lifecycle
- [Django App Map](architecture/django-app-map.md) — all 18 apps: models, dependencies, services, selectors, rules
- [Frontend Architecture](architecture/frontend-architecture.md) — Tailwind/Alpine/HTMX stack, templates, static pipeline
- [Theme Architecture](architecture/theme-architecture.md) — DB → CSS variables → Tailwind (the dynamic theming answer)
- [Security Architecture](architecture/security-architecture.md) — entry point tying auth, authorization, audit, privacy together
- [Integration Architecture](architecture/integration-architecture.md) — external system boundary pattern (not built yet)
- [Deployment Architecture](architecture/deployment-architecture.md) — environments, secrets, backups, observability

## Database

- [Database Conventions](database/database-conventions.md) — PK/FK strategy, indexing, constraints, soft delete, audit fields
- [Domain Model](database/domain-model.md) — core entity relationships, the Person/Employee/User split
- [Data Lifecycle](database/data-lifecycle.md) — effective dating mechanics, retention

## Security

- [Authentication](security/authentication.md) — Entra ID / django-allauth, break-glass fallback
- [Authorization](security/authorization.md) — Groups/Permissions + UserScope, policy layer, worked examples
- [Audit](security/audit.md) — django-simple-history + custom AuditLog hybrid

## Frontend

- [Design System](frontend/design-system.md) — tokens, typography, light/dark
- [Component Architecture](frontend/component-architecture.md) — the full reusable component inventory
- [Theme System](frontend/theme-system.md) — ThemeConfiguration, ThemeService, `/theme.css`, Theme Studio UX

## Development

- [Coding Standards](development/coding-standards.md) — Python/Django/services/selectors/templates/JS/URL conventions
- [Testing Strategy](development/testing-strategy.md) — pytest-django, Playwright, what's tested at each layer
- [Git Strategy](development/git-strategy.md) — branching, commits, migration review policy

## Architectural Decision Records

| ADR | Decision |
|---|---|
| [001](adr/ADR-001-modular-monolith.md) | Modular monolith, not microservices |
| [002](adr/ADR-002-postgresql.md) | PostgreSQL |
| [003](adr/ADR-003-uuid-strategy.md) | BigAutoField PK + `public_id` UUID on user-facing models |
| [004](adr/ADR-004-server-rendered-ui.md) | Server-rendered UI, no SPA |
| [005](adr/ADR-005-htmx-alpine.md) | HTMX + Alpine.js |
| [006](adr/ADR-006-dynamic-theme-architecture.md) | DB-driven theme via CSS variables, static Tailwind classes |
| [007](adr/ADR-007-authorization-model.md) | Groups/Permissions + scope-based UserScope |
| [008](adr/ADR-008-effective-dating.md) | Effective-dated history with DB-enforced non-overlap |
| [009](adr/ADR-009-audit-strategy.md) | Hybrid django-simple-history + custom AuditLog |
| [010](adr/ADR-010-background-task-strategy.md) | Celery + Redis, wired in on first real need |

See the project's final Phase 00 summary (delivered in chat/plan output) for the Technology Stack table, Risks, Assumptions, Open Questions, and the READY/NOT READY verdict.
