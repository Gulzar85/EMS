# Deployment Architecture

Status: Phase 00 architecture baseline. Defines target environments, secrets handling, and deploy/rollback discipline for the Django-based EMS. **No deployment scripts or pipelines are written as part of this phase** — this document defines the target shape those scripts must follow once they are built.

Related documents:
- [Git Strategy](../development/git-strategy.md)
- [Database Conventions](../database/database-conventions.md)
- [Integration Architecture](./integration-architecture.md)
- [Frontend Architecture](./frontend-architecture.md)

## 1. Environments

| Environment | Purpose | Distinguishing characteristics |
|---|---|---|
| **Development** | Local developer machines | Local/`docker-compose` PostgreSQL + Redis. `settings/dev.py`, `.env` file (gitignored). `DEBUG` on, human-readable console logging, local filesystem for media. |
| **Testing (CI)** | Automated test runs on every PR | Ephemeral, disposable database created fresh per CI run. `settings/test.py`. No persistent state between runs — every run starts from migrations, not a snapshot. |
| **Staging** | Pre-production validation | Production-like configuration (same settings module family, same infrastructure shape as production) but populated with **anonymized/synthetic HR data — never real employee PII**. This is the environment used for UAT, demo, and pre-release validation without exposing real people's data outside production access controls. |
| **Production** | Live system of record | Real employee data, tightened access (see [Authentication](../security/authentication.md) and scope model in [Coding Standards](../development/coding-standards.md)), the only environment where real PII is permitted to exist. |

Promotion flows one direction: Development → Testing (CI, on every PR) → Staging (on merge to `main`) → Production (manual promotion). See [Git Strategy §4](../development/git-strategy.md#4-environment-to-branch-mapping) for the branch-to-environment mapping.

## 2. Environment variables and secrets

- **Local development** reads configuration from a `.env` file via **django-environ**. `.env` is gitignored and never committed — each developer maintains their own local copy (an `.env.example` with placeholder keys, no real values, is the shareable template).
- **Testing, Staging, and Production never use a `.env` file.** They receive configuration as environment variables injected by the hosting platform's own secret store.
- **Assumption:** given the Microsoft-centric stack (Entra ID/OIDC, Windows-oriented team), the hosting platform is assumed to be **Azure App Service with secrets sourced from Azure Key Vault** (referenced into App Service configuration). This is an assumption pending an actual infrastructure/hosting decision — if the organization selects a different host, this section's mechanism changes but the principle (no secrets in source control, ever, in any environment) does not.
- `SECRET_KEY`, database credentials, the Redis connection string, and the Entra ID client secret are **all environment-sourced** in every non-local environment — none of them ever appear in a settings file, a migration, a fixture, or a log line.

## 3. Database migrations

- Migrations are applied as an **explicit deploy step**, run once as part of the release process — **never on every application boot**. Running migrations on boot is unsafe with more than one app instance (multiple instances racing to apply the same migration) and hides schema changes inside application startup logs instead of the deploy log where they belong.
- Migration content is reviewed per the policy in [Git Strategy §3](../development/git-strategy.md#3-migration-review-policy) — every model-changing PR ships its migration in the same PR, reviewed against [Database Conventions](../database/database-conventions.md).
- **Target discipline: backward-compatible-first migrations**, so a deploy can proceed without downtime and so the previous release's code keeps working against the new schema for the duration of a rolling deploy:
  - Adding a column: add it **nullable** first, backfill data in a follow-up step (a management command or a one-off script, not inline in the migration for large tables), then tighten to `NOT NULL` in a later migration once backfill is confirmed complete.
  - Renaming a column: implemented as add-new → dual-write/backfill → switch reads → drop-old across multiple deploys, not a single rename migration — a straight rename breaks any code from the previous release still running during a rolling deploy.
  - This mirrors the destructive-migration callout requirement in [Git Strategy §3](../development/git-strategy.md#3-migration-review-policy): if a migration can't be done this way, that's exactly the case that needs an explicit callout and a documented backfill/rollback plan in the PR.

## 4. Static and media files

- **Static files** (CSS built by the Tailwind pipeline — see [Frontend Architecture](./frontend-architecture.md) — plus JS, Alpine components, vendor assets) are built at deploy time and served via Django's `collectstatic` step, fronted by a CDN or a storage-backed static host (or WhiteNoise as a simpler baseline) — not served from the application process's own ephemeral disk in a way that assumes a single, persistent instance.
- **Media files** (employee photos, uploaded documents) are served via **django-storages**, pointed at **Azure Blob Storage in Staging and Production**. This is not optional in those environments: application instances are treated as ephemeral (they can be replaced/restarted/scaled at any time), so anything written to local disk would be lost on the next instance cycle. **Local filesystem storage for media is acceptable in Development only.**

## 5. Backups

- **PostgreSQL:** automated daily backups plus point-in-time recovery. **Assumption:** a managed Postgres offering (e.g. Azure Database for PostgreSQL — Flexible Server) provides this out of the box, consistent with the Azure hosting assumption in [§2](#2-environment-variables-and-secrets). This is an assumption pending confirmation of the actual hosting decision, not a guarantee already in place.
- **Media/blob storage:** assumed to have its own redundancy from the cloud provider (e.g. Azure Blob Storage's built-in replication options) rather than a separate application-level backup process. Also stated as an assumption pending the same hosting confirmation.

## 6. Logging and observability

- **Structured JSON logging** in Staging and Production — machine-parseable log lines suitable for a log aggregation platform, not the human-formatted console output used in Development.
- A **request correlation ID** is generated in `core` app middleware for every incoming request and threaded through: application logs for that request, and any `AuditLog` entries (see the `audit` app) written during that request — so a single request's full story (what happened, who did it, what got logged where) can be reconstructed from the correlation ID alone.
- **Sentry** is evaluated and **Recommended** for error tracking: it catches unhandled exceptions with full request context, has mature first-party Django integration, and has a free/low-cost tier that comfortably fits this system's scale. Not mandated as the only option, but the clear default recommendation absent a reason to choose otherwise.
- A **health-check endpoint** (`/healthz/`) checks database and Redis connectivity and is used by the hosting platform's liveness/readiness probes to decide whether an instance is healthy.
- **Background job monitoring** (Celery Flower, or the hosting platform's own task dashboard) is **Phase 01+**, once Celery is actually wired in for a real async need — there's nothing to monitor before then, so this is noted here as the target shape rather than something to stand up now.

## 7. Deployment strategy

No deployment scripts or CI/CD pipeline are written in this phase — that is explicitly out of scope for this architecture package. The target shape they should eventually implement:

- **Containerized (Docker) build artifact** — the application is packaged as a container image, not deployed from a raw checkout on the host.
- Deployed via the hosting platform's **standard rolling-deploy mechanism** (e.g. Azure App Service's built-in deployment slots/rolling restart), so new instances come up and old ones drain rather than all instances restarting simultaneously.
- **Migrations run as a pre-deploy or release-phase step**, executed once against the target database before (or as a discrete phase ahead of) the new application instances start serving traffic — never as code inside the running web process (see [§3](#3-database-migrations)).

## 8. Rollback strategy

- **Primary rollback path: redeploy the previous container image/release.** Because deploys are versioned build artifacts (not in-place file edits), rolling back is "run the previous image" — no special rollback tooling required.
- Migrations should be written to be **safely rollback-compatible** wherever feasible — this is the same backward-compatible-first discipline from [§3](#3-database-migrations): if the previous release's code needs to run again after a rollback, it must still work against whatever the current schema looks like. This is exactly why destructive migrations (drops, renames) require the explicit backfill/rollback note called for in [Git Strategy §3](../development/git-strategy.md#3-migration-review-policy) — a migration with no rollback note is a migration that hasn't been vetted for this scenario.
- **Full database point-in-time restore is a last-resort path**, used only for a rollback that must also undo *data* changes (not just code/schema), not a routine deployment tool. Reaching for a PITR restore as a normal rollback step would mean discarding all writes made since the deploy — acceptable only when the alternative is worse (e.g. a bug that corrupted data at scale), and always a deliberate, explicit decision rather than an automated response to a bad deploy.
