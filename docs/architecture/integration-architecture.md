# Integration Architecture

Status: Phase 00 architecture baseline.

**No integrations are built in Phase 00 or Phase 01.** This document defines the boundary and pattern that future integrations must follow when they arrive — it is a design contract for `integrations`, not a description of anything currently wired up. Authentication via Entra ID is the one exception already in scope for Phase 01, and it is covered in [Authentication](../security/authentication.md), not here — this document only cross-references it.

Related documents:
- [Deployment Architecture](./deployment-architecture.md)
- [Authentication](../security/authentication.md)
- [Database Conventions](../database/database-conventions.md)

## 1. Purpose

Every external system the EMS will eventually talk to — Entra ID, Dynamics 365 F&O, a biometric attendance reader, Power BI, Teams — has a different data model, a different identifier scheme, and its own failure modes. Without a deliberate boundary, that vendor-specific mess leaks into domain apps: an `Employee` model grows a `d365_employee_id` column, an `AttendanceRecord` grows a `biometric_device_punch_id`, and suddenly the `employees` and `attendance` apps can't be understood, tested, or changed without knowing about systems that have nothing to do with what they actually model.

The `integrations` app exists so that never happens. **Domain apps model the business; the `integrations` app models the outside world's opinions about the business.**

## 2. Model design

All of the following live in the `integrations` app.

### `ExternalSystem`
Represents one external system the EMS integrates with.

- `name` — e.g. `"Entra ID"`, `"D365 F&O"`, `"Biometric Attendance Reader Model X"`.
- `type` — a category (identity provider, ERP, biometric device, BI tool, notification channel) used for grouping/filtering, not for driving integration-specific code paths from a single generic model.

### `ExternalIdentifier`
The generic mapping table — this is the mechanism that keeps external IDs out of domain models entirely.

- FK to `ExternalSystem`.
- A reference to the internal entity it maps to. Either:
  - Django's generic relation (`content_type` + `object_id`), or
  - An explicit `entity_type` string + the internal entity's `public_id` (UUID) — preferred where practical, since it avoids `ContentType` indirection and reads clearly in the database (`entity_type="Employee", entity_public_id=<uuid>`), and pairs naturally with the system-wide `public_id` convention (see [Coding Standards](../development/coding-standards.md#12-url-architecture)) rather than the integer PK.
- `external_id` — the external system's own identifier string for that entity (a D365 employee code, an Entra `oid`, a biometric device's enrolled-user ID).
- `metadata` — optional JSON for anything system-specific worth keeping alongside the mapping (e.g. the external system's own last-modified timestamp, a sync cursor).

**Rule: external IDs are never used as this application's primary keys or foreign keys.** A domain model is never joined to by an external ID column living on that domain model — any "does this employee have a D365 mapping" question is answered by looking up `ExternalIdentifier`, not by checking a field on `Employee`.

### `IntegrationLog`
Records that a sync event happened, for observability and troubleshooting.

- `timestamp`, `system` (FK to `ExternalSystem`), `direction` (`in` / `out`).
- `payload_summary` — a **summary**, not the full payload. This log must never contain full PII (employee names, salaries, national ID numbers, biometric templates) — it records enough to debug a failed sync (record type, count, external ID, status) without becoming a second, unaudited store of sensitive HR data.
- `status` (success / failure / partial), `error_detail` (for failures).

### `SyncJob`
Represents a recurring or triggered synchronization job.

- `system` (FK to `ExternalSystem`), `job_type` (e.g. "attendance punch import", "employee export to D365").
- `schedule` / `trigger` — how it runs (cron-style schedule, or event-triggered).
- `last_run_status`, `next_run` — operational state for monitoring.
- Execution ties into the **Celery + Celery Beat** background-task architecture described in [Deployment Architecture](./deployment-architecture.md#6-logging--observability) — a `SyncJob` is the persisted record of what should run and when; Celery Beat is the scheduler that actually triggers it, and a Celery task is what executes it and writes the resulting `IntegrationLog` entries.

## 3. Isolation pattern

- The `integrations` app owns `ExternalSystem`, `ExternalIdentifier`, `IntegrationLog`, and `SyncJob` outright. No other app defines its own external-ID fields or its own sync bookkeeping.
- **Domain apps (`employees`, `attendance`, `compensation`, etc.) never import from `integrations`, and never store an external ID directly on their own models.** The dependency direction is one-way: `integrations` knows about domain apps' `public_id`s (to build mappings), but domain apps do not know `integrations` exists.
- When a domain app needs to know "is this employee synced to D365?", it asks `integrations`' own selector (e.g. `integrations.selectors.get_external_identifier(entity_type="Employee", entity_public_id=employee.public_id, system_name="D365 F&O")`) rather than reading a field off its own model. This keeps the query pattern consistent with the rest of the system's selector convention (see [Coding Standards](../development/coding-standards.md#8-selectors)) — it just happens that the "read" is answering a cross-app integration question rather than a domain question.
- **Consequence:** an integration can be added, swapped, or retired — Entra ID replaced, a biometric vendor changed, D365 migrated to a successor ERP — by changing only the `integrations` app and its `SyncJob`/`ExternalIdentifier` rows. No domain app migration is required, because no domain model ever encoded a dependency on that vendor in the first place.

## 4. Future integrations — brief notes

None of the following are built yet. These notes exist so the shape above is validated against real anticipated needs, and to flag open questions early.

| System | Direction | Notes |
|---|---|---|
| **Entra ID / Microsoft Graph** | Auth | Already covered as authentication, not a data integration — see [Authentication](../security/authentication.md). This document only notes that Entra ID is also registered as an `ExternalSystem` row if/when Graph API calls beyond login (e.g. profile photo sync) are added later. |
| **Dynamics 365 F&O** | Outbound (likely) | Likely payroll/cost-center sync — outbound employee and cost-center data from the EMS toward D365. Exact scope depends on what McDonald's Pakistan's finance/payroll process actually needs from the EMS versus the other direction. |
| **Payroll** | Outbound (likely) | Salary data outbound, likely routed via D365 or a dedicated payroll system — **which one is actually in use at McDonald's Pakistan is TBD/open question** and should be confirmed before this integration is designed further; do not assume D365 is the payroll system of record. |
| **Attendance / Biometric devices** | Inbound | Inbound punch/clock events. Likely the **highest-volume** integration in the system (potentially thousands of punches per day across restaurants), and a strong candidate for the `SyncJob` + Celery pattern — polling or receiving device exports on a schedule rather than a live synchronous call per punch. |
| **Power BI** | Outbound (reporting) | Likely served via a **read replica or scheduled export**, not live API access against the OLTP database — protects production query performance from analytics load. Exact export mechanism (replica connection, nightly extract, dataset push) is a later decision. |
| **SharePoint** | Storage (possible) | A possible target for document storage. **Open question:** SharePoint versus using django-storages' Azure Blob Storage support directly (see [Deployment Architecture](./deployment-architecture.md#4-static--media-files)) for the `documents` app's files — Blob Storage is the simpler, more directly-integrated option and is the current default assumption for media, but SharePoint may be preferred if the business wants documents visible/manageable inside existing SharePoint workflows. Not decided. |
| **Microsoft Teams** | Notification channel only | Not a data integration — a delivery channel for the `notifications` app (e.g. a leave-approval notification posted to Teams instead of, or in addition to, email). Ties into `notifications` app design, not into `ExternalIdentifier`/`SyncJob` machinery, since Teams isn't a system EMS data is being reconciled against. |
