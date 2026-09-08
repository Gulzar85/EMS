# ADR-002: PostgreSQL as the Primary Database

## Status

Accepted

## Context

EMS requires a relational database capable of enforcing complex relational integrity — organizational hierarchies, effective-dated history, referential constraints — with rich constraint types and enterprise-grade reliability. The database is foundational to nearly every other architectural decision in this system, including effective dating (ADR-008) and dynamic theming (ADR-006).

## Decision

EMS will use **PostgreSQL** as its primary database, making deliberate use of `django.contrib.postgres` features rather than treating Postgres as a generic SQL store. Specifically:

- **`ExclusionConstraint`** to prevent overlapping effective-dated periods at the database level (see ADR-008).
- **`JSONField`** for flexible, semi-structured data such as theme tokens and configuration payloads that don't warrant a fully normalized schema.
- **Trigram (`pg_trgm`) and GIN indexes** to support fast, fuzzy HR search (e.g., searching employees by partial name).

## Alternatives Considered

- **MySQL / MariaDB** — rejected. Weaker native support for exclusion constraints and range types needed for effective-dating, which would push overlap-prevention logic into the application layer and forfeit database-level correctness guarantees.
- **SQL Server** — rejected, though acknowledged as a fair counterpoint given McDonald's broader Microsoft-centric stack (Dynamics 365, Entra ID). There is no strong technical reason to add a second Microsoft-licensed database engine's cost and operational profile when PostgreSQL does the job well and is where the Django ecosystem is most mature and polished. The Django/Postgres ecosystem's maturity for this specific workload wins out over stack homogeneity alone.
- **NoSQL / document databases** — rejected. This domain is fundamentally relational: org hierarchies, effective-dated history, and referential integrity constraints are a poor fit for schemaless stores, which would require reimplementing relational guarantees in application code.

## Consequences

**Positive:**
- Database-enforced effective-dating correctness via exclusion constraints, not just application-level validation.
- Rich indexing options (GIN, trigram) support HR search use cases without bolting on a separate search engine.
- Mature, well-supported Django ORM integration reduces implementation risk.

**Negative / Tradeoffs:**
- If the organization's operational default leans toward SQL Server/Microsoft-stack tooling, PostgreSQL is an additional engine type for the ops team to run, patch, and back up. This is mitigated by using a managed PostgreSQL service (e.g., Azure Database for PostgreSQL) rather than self-hosting, which shifts most of that operational burden to the cloud provider.
