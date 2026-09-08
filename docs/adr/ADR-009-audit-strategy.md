# ADR-009: Audit Strategy

## Status

Accepted

## Context

The architecture brief requires audit trails for a substantial list of sensitive actions: employee CRUD, position/restaurant/manager changes, promotions, salary changes, leave approvals, terminations, document verification, permission changes, and theme/configuration changes. Each audit record must capture the actor, timestamp, action, entity, old and new values, IP address, a human-readable reason, and a correlation ID linking related changes together.

## Decision

EMS uses a **hybrid audit strategy** combining two complementary mechanisms, both written inside the same database transaction as the change they describe:

1. **`django-simple-history`** applied to sensitive/historical models, giving automatic, low-effort, field-level "what changed" diffs per model instance.
2. A custom **`audit` app with an `AuditLog` model** recording business-event-level "what happened" — including events that are not simple field diffs (a login failure, a document verification, a leave approval that touches multiple models) and carrying the reason, IP address, and correlation ID that `simple-history` has no natural place for.

## Alternatives Considered

- **`django-simple-history` alone** — rejected. It gives field-level diffs per model instance but has no natural way to represent a single business *event* that spans multiple models or that carries a human-readable reason, IP address, or correlation ID. For example, "leave approved" touches both `LeaveRequest.status` and `LeaveBalance.remaining_days` as one coherent event; `simple-history` alone would only show two separate, uncorrelated row diffs with no record of *why* the approval happened.
- **A fully custom audit system with no `django-simple-history`** — rejected. This would mean reinventing well-tested field-diff tracking, adding code to write and maintain for something `simple-history` already handles well.
- **An external audit/SIEM-only approach** (logging events exclusively to an external system) — rejected as the *sole* mechanism. HR and Compliance need queryable, in-app audit history on their own screens, not only an external log stream. Shipping audit events to a central log/SIEM system in addition, for security monitoring, is a reasonable future addition — not a replacement for an in-app audit trail.

## Consequences

**Positive:**
- Gets both automatic, low-effort field-level history (via `simple-history`) and a clean, readable business-event trail with reason and context (via `AuditLog`) that HR and Compliance staff can actually query and understand.

**Negative / Tradeoffs:**
- Two audit mechanisms exist side by side and must be kept conceptually consistent. This is mitigated by documenting, in `../security/audit.md`, a mapping table of which service writes which `AuditLog` action, combined with code review ensuring every service on the required-audit list actually writes an audit record.
- The `AuditLog` table itself needs its own access control and tamper-resistance measures — no application role is granted update or delete permission on it, since an audit trail that can be edited or removed by the system it audits is not trustworthy.
