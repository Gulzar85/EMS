# Tailwind CSS

Status: **Implemented**. Tailwind v4.3.3, via `@tailwindcss/cli` — no `tailwind.config.js` (v4's CSS-native config), no CDN build in any environment.

Related: [Theme System](theme-system.md), [Design System](design-system.md), [ADR-006](../adr/ADR-006-dynamic-theme-architecture.md).

## Build

```bash
npm install        # once — @tailwindcss/cli + tailwindcss, the only two npm deps
npm run build:css   # one-shot, minified
npm run watch:css    # dev
```

Entry point: `static/src/css/app.css`. Output: `static/dist/css/app.css` (the only thing `STATICFILES_DIRS` points to — `static/src/` is never served directly).

```css
@import "tailwindcss";
@source "../../../templates";
@source "../../../apps";

@theme {
  --color-brand: #da291c;
  /* ... every design token ... */
}
```

`@source` directives are explicit because Tailwind v4's automatic content detection is tuned for typical JS-framework project layouts, not a Django template tree — without them, classes used only in `.html` files under `templates/`/`apps/` could be purged.

## Why v4, not v3

Tailwind v4's headline feature — theme variables are real CSS custom properties, and generated utilities *reference* them (`color: var(--color-brand)`) rather than inlining a resolved value — is exactly the mechanism the whole dynamic theme engine depends on ([ADR-006](../adr/ADR-006-dynamic-theme-architecture.md)). This wasn't available the same way in v3's JS-config model.

## The naming-collision rule (read before adding a new color token)

Tailwind auto-generates `bg-`/`text-`/`border-`/... utilities from every `--color-{name}` variable in `@theme`. Two *different* semantic concepts can't both claim the same short name (e.g. "primary" meaning both "brand action color" and "default text color"). See the comment block at the top of `app.css` and [Design System §1.1](design-system.md) for the resolution already in place (`--color-brand` vs `--color-primary`-as-text). Before naming a new token, check it doesn't collide with an existing one under this auto-generation rule.

## Never generate class names from data

The one hard rule this whole system exists to satisfy: **no template ever builds a Tailwind class name from a database value** (`bg-{{ theme.color }}` is forbidden, would silently do nothing even if it "looked" like it should work, since Tailwind only ever generates CSS for class strings it can see literally in source at build time). Only CSS variable *values* are dynamic; class *names* are always static strings written directly in template/component source. `apps/theme/rendering.py` renders variable values into a separate stylesheet (`/theme.css`) — it never touches which classes exist.

## Production output

`npm run build:css --minify` (wired into `npm run build`) produces a single minified file containing only the utilities actually referenced in `templates/`/`apps/` — confirmed in Phase 01/02 testing by grepping the built output for expected classes (`bg-brand`, `text-primary`, `border-default`) and confirming they compile to `var(--color-*)` references, not inlined hex values.
