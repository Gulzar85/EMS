# ADR-003: Primary Key and Public Identifier Strategy

## Status

Accepted

## Context

Across roughly 18 domain apps, EMS needs a consistent primary-key strategy that balances two competing concerns: database performance (join cost, index size, insert locality) and security (the risk of sequential integer IDs being enumerable when exposed in URLs or APIs — e.g., `/employees/1042/` implicitly reveals that `/employees/1041/` likely exists, and can leak headcount information through ID gaps over time).

## Decision

- **`BigAutoField`** is the real primary key on every model, everywhere. It is compact (8 bytes), fast to index and join, and inserts in sequential order, which matters for high-volume child tables.
- A separate, unique, indexed **`public_id` (UUID4)** field is added *only* to models that are addressed directly by a URL or a future API — e.g., `Employee`, `Person`, `Document`, `LeaveRequest`, and similar user/externally-facing entities.
- Internal foreign keys always reference the integer primary key. URLs and any future API surface always resolve and reference records by `public_id`, never by the integer PK.

## Alternatives Considered

- **UUID as the primary key everywhere** — rejected. A 16-byte UUID FK/index is roughly double the size of an 8-byte integer, and random UUID insert order causes B-tree fragmentation on high-volume child tables (e.g., `AttendanceRecord` at 10M+ rows). This cost buys collision-free client-generated IDs across distributed writers — a capability EMS does not need at its actual scale of a single organization with thousands of employees, not a multi-region distributed-writer system.
- **Plain integer PK exposed directly in URLs** — rejected. It is enumerable: sequential IDs in URLs let anyone infer the existence of adjacent records and estimate headcount or record volume from ID gaps.

## Consequences

**Positive:**
- Fast joins and compact indexes on high-volume tables, since the "real" relational backbone of the system stays integer-based.
- Non-enumerable, opaque public identifiers exactly where they matter (anything reachable by URL or API), without paying the UUID-as-PK cost everywhere.

**Negative / Tradeoffs:**
- Every user-facing or URL-facing model carries the extra cost of a second identifier field (`public_id`) plus the discipline required to always resolve and route by `public_id` in views and URL configuration, and to never accidentally leak the integer PK (e.g., via a stray `pk` reference in a URL or serialized payload). This is mitigated by documenting the URL convention in `../development/coding-standards.md` and enforcing it through code review.
