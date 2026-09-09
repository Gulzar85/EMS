# Theme Development

How to extend the theme engine. See [docs/frontend/theme-system.md](../frontend/theme-system.md) for how it currently works, and [theme-security.md](../frontend/theme-security.md) before touching validation.

## Add a new color token

1. Add the name to `COLOR_TOKENS` in `apps/theme/validation.py`.
2. Add its CSS variable mapping to `_CSS_VAR_NAME` in `apps/theme/rendering.py`. If it should differ between light and dark, add it to `_MODE_VARYING_COLORS` too.
3. Add the variable's static default to `static/src/css/app.css`'s `@theme` block (the fallback used before any `Theme` is published, and the base value Tailwind's utility generation needs to exist at build time).
4. Add the field pair to `ThemeStudioForm.__init__` in `apps/theme/forms.py` (it's generated in a loop from `COLOR_TOKENS`, so this is usually automatic — check the loop still covers it).
5. Add it to `DEFAULT_THEME_TOKENS` in `apps/theme/validation.py` **and** to the seed migration's copy of the same dict (`apps/theme/migrations/0002_seed_default_theme.py` — deliberately not imported from `validation.py`, since data migrations should stay frozen in time; update both by hand).
6. Do **not** bump `CURRENT_SCHEMA_VERSION` for an additive, backward-compatible change like this — existing published `ThemeVersion` rows are simply missing the new key until their next draft edit fills it in via the form. Bump it only for a breaking change (renaming or removing a key, changing a value's expected shape).

## Add a new token *section* (e.g. "shadows")

Same as above, plus: add the section name to `_KNOWN_TOP_LEVEL_KEYS` in `validation.py`, write a `_validate_shadows()` function following the same closed-set pattern as `_validate_radius()`, and call it from `validate_theme_tokens()`. This is a bigger change — bump `CURRENT_SCHEMA_VERSION` and write a data migration that adds the new section (with sensible defaults) to every existing published `ThemeVersion.tokens`, since old versions won't have it and `render_theme_css()` will simply skip anything missing rather than error, which is safe but means old versions won't render the new tokens until backfilled.

## Add a new cotton component

Follow the existing pattern in `templates/components/*.html` — `{% cotton:vars ... %}` for defaults, `{{ attrs }}` spread for pass-through HTML attributes, `{{ slot }}` for default content, `<c-slot name="x">` for named slots. Add it to the Styleguide page (`templates/theme/styleguide.html`) and to the inventory table in [docs/frontend/components.md](../frontend/components.md). **Use only single-line `{# #}` comments** — see the gotcha noted in that same doc.

## Testing a change

- `apps/theme/tests/test_validation.py` / `test_rendering.py` — schema and CSS-injection tests. Add a case for any new token type's malicious/malformed inputs.
- `apps/theme/tests/test_services.py` — if the change touches `create_theme`/`update_draft_tokens`/`publish_theme`.
- `apps/theme/tests/conftest.py` has two autouse fixtures worth knowing about: one deletes the seeded default `Theme` before every test (it would otherwise collide with any test-created `is_active=True` theme under the single-active constraint), the other clears the cache (LocMemCache persists across the whole test session, not per-test, and would otherwise leak `ThemeCacheService` state between tests).
- `transaction.on_commit()` callbacks (cache invalidation) don't fire under Django's default `TestCase` — use `TransactionTestCase` for anything that needs to observe that, as `ThemeCacheInvalidationTests` in `test_services.py` does.

## Local Postgres note

The `theme_single_active` and `uniq_theme_version_number` constraints are real Postgres constraints (a partial unique index and a composite unique index respectively) — they only exist after migrations run, and they're what actually prevents two concurrent publishes from both succeeding (see [Theme System §2](../frontend/theme-system.md)). Don't remove or weaken them without re-reading the Phase 02 plan's concurrency section.
