# ADR-006: Dynamic Theme Architecture

## Status

Accepted

## Context

The architecture brief requires that the entire visual theme — colors, typography, layout, component appearance — be configurable by an administrator from the database, without a code change or a rebuild/redeploy. At the same time, EMS uses Tailwind CSS, which generates its utility classes at **build time** by statically scanning source files for class-name usage. A value stored in the database cannot safely materialize into a brand-new Tailwind class at runtime — Tailwind's JIT compiler will never have "seen" that class name during the build, so it will not exist in the compiled CSS.

## Decision

EMS resolves this tension with a layered design:

1. A `ThemeConfiguration` database model stores the admin-controlled theme values.
2. A `ThemeService` renders those values into CSS custom properties (e.g., `--color-primary: #DA291C;`).
3. These properties are served from a versioned `/theme.css` endpoint (versioned/cache-busted so updates propagate immediately).
4. All component templates use a **fixed, static set of Tailwind utility classes** that reference those CSS variables through Tailwind's arbitrary-value syntax, e.g. `bg-[var(--color-primary)]`.

Because the class strings themselves (`bg-[var(--color-primary)]`) are static and present in the source templates, Tailwind's build-time scanner sees and pre-generates CSS for them normally. What changes at runtime is only the **value** the CSS variable resolves to — never the set of classes in use.

## Alternatives Considered

- **Storing raw Tailwind class names in the database** — rejected. This violates Tailwind's build-time JIT scanning model: an admin-entered class such as `bg-blue-500` that was never referenced anywhere in the source templates will not have been generated into the build output, and will silently render unstyled in production. It is also uncomfortably close to a code-injection pattern — rendering admin-supplied strings directly as CSS classes.
- **A full runtime CSS-in-JS / styled-components approach** — rejected. Foreign to the Django/Tailwind/server-rendered stack chosen in ADR-004 and ADR-005; it adds an entire JS runtime dependency to solve a problem CSS custom properties already solve natively and more simply.
- **Rebuilding Tailwind's static assets on every admin theme save** — rejected. Rebuilding and redeploying static assets on every theme tweak is operationally heavy, slow, and incompatible with a "live preview" theme-studio experience that admins expect to feel instant.

## Consequences

**Positive:**
- Theme changes take effect instantly — a CSS variable rewrite plus a cache-bust, with no rebuild or redeploy required.
- Tailwind's JIT/purge behavior is fully preserved, so production CSS output stays minimal and predictable.
- Clean separation of concerns: *which CSS properties exist* is fixed and code-reviewed; *what values they hold* is dynamic and admin-controlled.

**Negative / Tradeoffs:**
- The set of themeable properties is bounded by which CSS variables the component templates were deliberately written to reference. An administrator cannot introduce an entirely new visual property (for example, a gradient background style that no template currently exposes as a variable) without a code change to add that CSS variable to the relevant component template first. This is treated as an acceptable, deliberate boundary: the theme system customizes *values* within a designed system, not arbitrary new component styles.
