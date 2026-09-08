# Git Strategy

Status: Phase 00 architecture baseline. Defines branching, commit, and migration-review conventions for the Django-based EMS.

Related documents:
- [Coding Standards](./coding-standards.md)
- [Testing Strategy](./testing-strategy.md)
- [Database Conventions](../database/database-conventions.md)
- [Deployment Architecture](../architecture/deployment-architecture.md)

## 1. Branching model

**Trunk-based development with short-lived feature branches off `main`.** There is no long-running `develop` branch (see [Environment-to-branch mapping](#4-environment-to-branch-mapping) for why).

- All work happens on a branch cut from `main`, kept as short-lived as practical — merged within days, not weeks, to avoid drift and painful merges.
- **No direct pushes to `main`.** Every change lands via a pull request that has been reviewed and approved before merge.
- Branch naming:
  - `feature/<app>-<short-desc>` — e.g. `feature/employees-transfer-flow`, `feature/leave-balance-accrual`.
  - `fix/<short-desc>` — e.g. `fix/scope-leak-restaurant-selector`.
  - Other prefixes (`chore/`, `docs/`) are fine for non-feature work following the same `<prefix>/<short-desc>` shape.

## 2. Commit conventions

**Conventional Commits** style is recommended for changelog-friendliness and a readable `git log`:

```
feat: add employee transfer service
fix: correct overlapping-assignment exclusion constraint
refactor: extract leave balance calculation into selector
docs: cross-reference database conventions from coding standards
test: add scope-filtering tests for get_employees_for_user
chore: bump ruff version
```

This is **recommended, not enforced by tooling, in Phase 00** — there is no commit-lint hook blocking a non-conforming message today. Adding a `commitlint`-style pre-commit hook to enforce the format mechanically is **Optional/future**, worth doing once the convention has proven itself useful in practice rather than mandating tooling for it up front (consistent with the "no tool sprawl" stance in [Coding Standards §15](./coding-standards.md#15-tooling)).

## 3. Migration review policy

Django migrations are schema changes to a system of record for HR data — they get the same review rigor as the code that generates them:

- **Every PR that touches models must include its migration in the same PR.** A migration is never deferred to a follow-up PR — a merged model change with no accompanying migration leaves `main` in a state where `makemigrations --check` fails, which is exactly what the pre-commit hook in [Coding Standards §15](./coding-standards.md#15-tooling) exists to catch before it ever reaches review.
- Migrations are reviewed against the conventions in [Database Conventions](../database/database-conventions.md) — indexing choices, constraint definitions (including effective-dating `ExclusionConstraint`s), and cascade behavior on foreign keys are checked explicitly, not rubber-stamped because "Django generated it."
- **Destructive migrations** — column drops, column/table renames, or any change that can lose data or break a query mid-deploy — require an **explicit callout in the PR description**, including:
  - What data is affected and why the drop/rename is safe.
  - A data-backfill note, if applicable (e.g. a rename implemented as add-new-column → backfill → drop-old-column across multiple deploys rather than a single destructive step).
  - A rollback note describing how to recover if the migration needs to be reverted after deploy.

  This ties directly into the backward-compatible-first migration discipline described in [Deployment Architecture](../architecture/deployment-architecture.md#3-database-migrations) — a migration that can't be safely rolled back or that breaks the previous release's queries is a deploy risk, and the PR description is where that risk gets surfaced for review, not discovered in production.

## 4. Environment-to-branch mapping

- **`main`** deploys to **Staging** automatically on merge.
- A **manual tag/release step** promotes a Staging-validated build to **Production** — production deploys are a deliberate action, not an automatic consequence of merging to `main`. See [Deployment Architecture](../architecture/deployment-architecture.md#1-environments) for what distinguishes each environment.
- **No `develop` branch.** Trunk-based development with short-lived feature branches is simpler to reason about at this team's size, and a long-running integration branch would add merge overhead without a corresponding benefit while there's a single team working out of one backlog. `develop` is marked **unnecessary unless and until multiple long-running feature efforts collide** (e.g. two teams each need weeks of integration time before either is release-ready) — if that happens, revisit this decision rather than introducing the branch preemptively.
