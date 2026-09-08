# ADR-001: Modular Monolith Architecture

## Status

Accepted

## Context

The Employee Management System (EMS) for McDonald's Pakistan spans approximately 18 distinct business domains — organization, employees, compensation, recruitment, attendance, leave, performance, training, and others — each with its own models, workflows, and rules. The system will be built and operated by a modest enterprise IT team, not a large distributed-systems organization with dedicated platform, SRE, and service-mesh capabilities.

We need an architectural style for structuring this much domain complexity that matches the team's actual operating capacity, supports strong data consistency across domains (e.g., an employee transfer that touches organization, compensation, and audit data simultaneously), and remains maintainable as the number of domains grows.

## Decision

EMS will be built as a **modular monolith**: a single Django project containing one `apps/<domain>` package per business domain, deployed as one unit against one database.

Cross-app access is permitted **only** through each app's public interface — its `services.py` (for writes/business operations) and `selectors.py` (for reads/queries). Direct cross-app ORM traversal (e.g., importing another app's model and querying it directly, or following a reverse relation across a domain boundary) is not permitted. This discipline is the load-bearing decision here: it is what keeps the codebase organized today and what keeps future extraction of a domain into its own service *possible*, should scale or organizational change ever require it.

## Alternatives Considered

- **Microservices** — rejected. At this org's scale and team size, the operational overhead of a service mesh, independent deployments, service discovery, and distributed transactions is unjustified. A single business operation such as an employee transfer touching Employee, Compensation, and Audit data would require saga/eventual-consistency patterns purely to compensate for the architecture, with no corresponding benefit.
- **A single flat Django app** with everything in one `models.py` / `views.py` — rejected. This does not scale conceptually to 18 domains; it has no enforced boundaries between concerns and reliably becomes a "big ball of mud" as the codebase grows.

## Consequences

**Positive:**
- Simple deployment and operations — one codebase, one release pipeline, one running unit to monitor.
- Cross-domain business transactions are trivial and genuinely consistent: a transfer touching employees, compensation, and audit is one real database transaction, not a distributed one.
- A single codebase is easy for a modest team to reason about, onboard into, and refactor.

**Negative / Tradeoffs:**
- The architecture must be self-policed. Nothing at the framework level stops a developer from importing another app's model directly and bypassing `services.py`/`selectors.py`. This is mitigated by code review discipline and by codifying the convention in the project's coding-standards documentation, but it is not a compiler-enforced guarantee.
- A monolith scales vertically and via read replicas rather than allowing one hot domain (e.g., attendance during shift-change peaks) to scale independently of the rest. This is an accepted tradeoff at EMS's expected data volume and traffic profile.
