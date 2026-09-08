# Design System

Status: Final (Phase 01 baseline)
Audience: Engineers and designers implementing UI for the EMS.

Related documents:
- [Frontend Architecture](../architecture/frontend-architecture.md)
- [Theme Architecture](../architecture/theme-architecture.md)
- [Theme System — implementation mechanics](theme-system.md)
- [Component Architecture](component-architecture.md)

This document describes the **design tokens** and **visual language** of the EMS. All token values shown are the seeded defaults (see [theme-system.md](theme-system.md) §6) and are runtime-configurable per [theme-architecture.md](../architecture/theme-architecture.md) — nothing here is hardcoded in templates as a literal value; everything is referenced via CSS custom properties.

---

## 1. Design Tokens Reference

### 1.1 Color roles and semantic meaning

Colors are defined as **roles**, not raw values, so templates never hardcode a hex code — they use the role, and the role's actual value is theme-controlled.

| Role | Variable | Semantic meaning | Typical usage |
|---|---|---|---|
| Primary | `--color-primary` | The brand/action color | Primary buttons, active nav item, links, focus rings |
| Primary hover | `--color-primary-hover` | Hover/active state of primary | Button `:hover` |
| Secondary | `--color-secondary` | Secondary brand accent | Secondary buttons, highlights |
| Accent | `--color-accent` | Tertiary emphasis color | Callouts, decorative accents |
| Background | `--color-background` | Page background | `<body>` background |
| Surface | `--color-surface` | Elevated container background | Cards, modals, tables, dropdowns |
| Text primary | `--color-text-primary` | Main body/heading text | Default text color |
| Text secondary | `--color-text-secondary` | De-emphasized text | Helper text, timestamps, metadata |
| Border | `--color-border` | Dividers and outlines | Table row dividers, input borders, card borders |
| Success | `--color-success` | Positive state | Success alerts, "Active" badges |
| Warning | `--color-warning` | Caution state | Pending approvals, expiring documents |
| Danger | `--color-danger` | Destructive/error state | Delete buttons, validation errors, "Terminated" badges |
| Info | `--color-info` | Neutral informational state | Informational alerts, "Draft" badges |

Every role above carries **both** a light and a dark value in `ThemeConfiguration` (see §2).

### 1.2 Typography scale

| Token | Variable | Notes |
|---|---|---|
| Font family | `--font-family-base` | Applied to `<body>`; a monospace fallback (`--font-family-mono`) is used only for IDs/codes/employee numbers |
| Base size | `--font-size-base` | `1rem` equivalent for body text |
| Heading scale | `--font-scale-ratio` | A modular ratio used to derive `--font-size-h1` … `--font-size-h6` from the base size, so the whole scale moves together when an admin adjusts one control |
| Weights | `--font-weight-normal` / `--font-weight-medium` / `--font-weight-bold` | Used consistently — body text at normal, labels/table headers at medium, headings at bold |
| Line height | `--line-height-base` | Applied globally; dense components (tables in compact mode) may use a tighter computed value |

### 1.3 Spacing / density scale

Spacing is expressed as multiples of a single `--spacing-unit` token rather than ad hoc pixel values, so the "Compact mode" toggle (§3) can rescale the entire application's density from one admin control:

| Density | `--spacing-unit` | Effect |
|---|---|---|
| Comfortable (default) | `0.25rem` | Generous padding, taller table rows, standard form field height |
| Compact | `0.1875rem` | Tighter padding, shorter table rows — useful for HR/Ops users scanning large employee lists |

Tailwind spacing utilities used in components (`p-4`, `gap-2`, etc.) are **not** replaced by the variable directly (Tailwind's own spacing scale is used for structural layout, since it's already themeable enough via fixed classes); `--spacing-unit` specifically drives the handful of density-sensitive components (table row height, form field height) that are declared with `padding: calc(var(--spacing-unit) * N)` in the component layer.

### 1.4 Elevation / shadow scale

| Token | Variable | Usage |
|---|---|---|
| Small | `--shadow-sm` | Inputs, badges on hover |
| Medium | `--shadow-md` | Cards, dropdowns |
| Large | `--shadow-lg` | Modals, command palette, popovers |

### 1.5 Radius scale

| Token | Variable | Usage |
|---|---|---|
| Button radius | `--radius-button` | Buttons, button-like controls |
| Card radius | `--radius-card` | Cards, stat cards, panels |
| Input radius | `--radius-input` | Text inputs, selects, date pickers |
| Badge radius | `--radius-badge` | Badges/pills (defaults to fully rounded) |

---

## 2. Light / Dark / System Handling

1. **Every color token has two stored values**: a light value and a dark value, both fields on `ThemeConfiguration` (e.g. `color_primary_light`, `color_primary_dark`).
2. **`ThemeService`** renders `/theme.css` with:
   - A `:root { --color-primary: <light value>; ... }` block (applies by default).
   - A `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --color-primary: <dark value>; ... } }` block, which applies automatically when the OS/browser is in dark mode, **unless** an explicit light override is present.
   - A `:root[data-theme="dark"] { --color-primary: <dark value>; ... }` block, which applies whenever the page has been explicitly switched to dark, **regardless of OS preference**.
3. **Precedence, in order**:
   1. Explicit user/admin choice (`data-theme="light"` or `data-theme="dark"` set on `<html>`, persisted e.g. in a cookie or user profile field) — always wins.
   2. `prefers-color-scheme` media query (System mode, the default when no explicit choice has been made).
   3. The light values as the ultimate fallback (base `:root`, no media query, no data attribute).
4. A small inline script in `base.html` (run before first paint, to avoid a flash of the wrong theme) reads the persisted preference and sets `data-theme` on `<html>` synchronously; this script only ever toggles an attribute — it never computes or hardcodes color values, which continue to come from `/theme.css`.
5. **Appearance mode is itself a `ThemeConfiguration`-adjacent setting** (`Light` / `Dark` / `System`), configurable at the application default level; a signed-in user may additionally override it for themselves, which is the "explicit override" referenced above.

---

## 3. Visual Language Principles

EMS is used by HR, Operations, Area/Regional Management, Finance/Payroll, Training, and employees, frequently against **large datasets** (hundreds of restaurants, thousands of employees). The visual language prioritizes clarity and scan-ability over decoration.

### Information density

- **Comfortable mode** (default): generous row height and padding, suited to occasional users and touch-adjacent laptop use.
- **Compact mode**: reduced row height/padding (via `--spacing-unit`, §1.3) for power users (HR/Payroll staff working through long employee or payroll-run lists all day) who benefit from seeing more rows per screen. Compact mode is a per-user or admin-default toggle, not a separate template — the same `templates/components/data_table.html` renders both densities purely through the spacing token.

### Accessible contrast

- **Target: WCAG 2.1 AA** contrast ratios (4.5:1 for normal text, 3:1 for large text/UI components) for all default token combinations (text-on-background, text-on-surface, text-on-primary). This is stated as a **goal/assumption pending final brand color sign-off** — because the actual production color values are an admin-configurable, brand-owned decision, AA compliance must be re-verified whenever the real McDonald's Pakistan brand palette is entered into Theme Studio, and the Theme Studio UX should surface a contrast warning when an admin picks a combination that fails AA (see [theme-system.md](theme-system.md) §5).
- Semantic colors (success/warning/danger/info) are never the *only* signal for state — an icon or text label always accompanies color-coded badges/alerts, for colorblind users.

### Consistent iconography

- **Lucide Icons** is the single icon set used everywhere (sidebar nav, buttons, status indicators, empty states). No mixing of icon libraries, so visual weight and stroke style stay consistent.
- Icons are rendered inline (SVG) so they can be styled with `currentColor` and pick up theme text/semantic colors automatically, rather than being colored image assets.
- Icon sizing follows a small fixed set (`16px` inline-with-text, `20px` standalone buttons, `24px` nav/section headers) rather than arbitrary per-instance sizes.

### Enterprise tone

- Minimal ornamentation: flat surfaces, subtle shadows (per the elevation scale, §1.4) rather than heavy drop shadows or gradients, consistent with a functional back-office HR tool rather than a consumer product.
- Motion is limited to functional transitions (dropdown/modal open-close, HTMX swap fade) — no decorative animation, to keep the tool feeling fast and serious for daily operational use.
