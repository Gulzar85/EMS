# ADR-010: Background Task Strategy

## Status

Accepted

## Context

EMS will eventually need asynchronous and scheduled work: notification delivery (email/Teams), document processing, expiry reminders (training certification, document expiry), data sync jobs once external integrations exist, and analytics/dashboard pre-aggregation. We need to decide both the *technology* for this and the *timing* of when to actually stand it up in the deployed infrastructure.

## Decision

EMS adopts **Celery, with Redis as the broker and result backend, and Celery Beat as the scheduler**, as its background-task technology of choice.

The architecture is put in place now, via a per-app `tasks.py` convention and Django signals that trigger `.delay()` calls at the appropriate points in each app's services. However, this stack is only actually **wired into deployed infrastructure once the first real asynchronous need lands in development** — expected to be notification delivery, early in Phase 01 — rather than being stood up speculatively on day one with nothing to run.

Redis is already a required dependency for caching and session storage, so adopting Celery introduces no new infrastructure *component*, only an additional worker *process* once it is actually needed.

## Alternatives Considered

- **`django-background-tasks` / Django-Q** — rejected. Smaller ecosystem, less battle-tested at enterprise scale, and no meaningful advantage over Celery once Redis is already a hard dependency for other reasons.
- **Doing everything synchronously in the request/response cycle** — rejected. Unacceptable for anything involving external email/Teams delivery or other slow I/O, which would block user-facing requests, and cannot support scheduled jobs (e.g., nightly expiry-reminder scans) at all.
- **A cloud-native scheduled-function service** (e.g., Azure Functions) instead of Celery Beat — rejected for this phase. It introduces a second deployment target and runtime outside the Django application for no clear benefit at this scale. This can be revisited only if serverless becomes the organization's broader standard.

## Consequences

**Positive:**
- Proven, well-documented tooling with strong Django integration (`django-celery-beat`, and optionally `django-celery-results` if database-backed schedule/result storage is preferred over Redis-only storage).
- No new infrastructure component is introduced beyond a worker process, since Redis already exists as a dependency for caching and sessions.

**Negative / Tradeoffs:**
- A worker process is another moving part to deploy, monitor, and scale independently of the web process once it is actually wired in. This operational cost is deliberately deferred until there is a real asynchronous workload to justify it, rather than being paid from day one for an empty task queue.
