# Theme Security

Status: **Implemented**. This is the complete CSS-injection defense for the dynamic theme engine — read this before touching `apps/theme/validation.py` or `apps/theme/rendering.py`.

Related: [Theme System](theme-system.md), [Authorization](../security/authorization.md), [Audit](../security/audit.md).

## The threat

Theme tokens are user-supplied (an admin, via Theme Studio) and get interpolated into a `<style>`/`text/css` response served to **every visitor**, authenticated or not. If a malicious or malformed value ever reached that interpolation point, it could break out of a CSS declaration and inject arbitrary CSS (data exfiltration via `background: url(...)`, page defacement, clickjacking overlays). `<script>`/`javascript:`/`expression(`/`url(` are exactly the payload shapes to worry about (Phase 02 plan §23).

## The defense: allow-list, not blocklist, checked twice

`apps/theme/validation.py:validate_theme_tokens()` accepts **only** values matching one of three exact patterns:

| Field type | Pattern | Example pass | Example reject |
|---|---|---|---|
| Color | `^#[0-9a-fA-F]{6}$` | `#DA291C` | `red`, `rgb(...)`, `#fff` (3-digit), `javascript:...` |
| Font family | `^[A-Za-z0-9 ,'\-]{1,200}$` | `'Inter', sans-serif` | anything containing `;`, `{`, `}`, `<`, `>`, `(`, `)`, `:` |
| Size (font size, radius) | `^\d+(\.\d+)?(px\|rem)$` | `16px`, `0.5rem` | `16`, `16em`, `-16px`, `16 px` |

Unknown top-level sections, unknown color keys, and a `schema_version` other than the currently supported one are all rejected outright — an admin cannot smuggle in an arbitrary nested structure "because JSONField allows it."

This is deliberately an **allow-list**, not a blocklist of dangerous substrings — a blocklist can always miss a payload shape its author didn't think of; an allow-list of "must be exactly one of these shapes" structurally cannot be bypassed by anything that isn't already one of those shapes.

**Checked twice**: once authoritatively when a service writes `tokens` (`update_draft_tokens`, `publish_theme`), and again — cheaply — in `apps/theme/rendering.py:render_theme_css()` immediately before string interpolation. The second check is defense-in-depth: it means a future code path that somehow writes to `ThemeVersion.tokens` without going through the service (a data migration, a bulk-admin script, a bug) still can't get an unsafe value into the CSS response — the renderer just silently skips that one declaration rather than emitting it.

## Tested

`apps/theme/tests/test_validation.py` and `test_rendering.py` assert each of the following is rejected: `<script>alert(1)</script>`, `javascript:alert(1)`, `expression(alert(1))`, a `background: url(javascript:...)` breakout attempt, a bare `red; } body { ... }` CSS-breakout attempt, 3-digit and 8-digit (alpha) hex shorthand, named CSS colors, `rgb()`/`rgba()` functions, and CSS-breakout attempts inside `font-family`. `apps/theme/tests/test_forms.py` confirms the same payloads are rejected at the form layer too (the first line of defense a real admin request hits).

## Where this does *not* apply

Theme metadata (`Theme.name`, `Theme.description`) is plain Django `CharField`/`TextField`, rendered through Django's template auto-escaping like any other text field in the app — it is never interpolated into CSS, so it doesn't need the same allow-list treatment; standard XSS protection (auto-escaping) is sufficient there.

## Audit trail

Every token change is recorded via `apps.audit.services.record()` with a `before`/`after` snapshot of the relevant fields (not the full token blob on every keystroke — only on an actual saved draft update or publish) — see [Audit](../security/audit.md) for the full mapping of theme actions to `AuditLog.action` values.
