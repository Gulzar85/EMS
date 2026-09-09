# HTMX

Status: **Implemented**. htmx 2.0.10, vendored as a single pinned file (`static/vendor/js/htmx.min.js`) — not an npm runtime dependency.

Related: [Frontend Architecture](../architecture/frontend-architecture.md), [Alpine.js](alpine.md).

## Conventions established in this project

### CBV + HTMX share one code path

Every mutating CBV in `apps/theme/views.py` uses the same `HtmxTemplateMixin` (`apps/core/mixins.py`): a normal `GET`/invalid-form `POST` renders the full-page template; the identical request with `HX-Request: true` renders the matching `templates/*/partials/*.html` fragment instead — same form, same service call, same validation, only the template resolution differs. No business logic is ever duplicated for the HTMX path.

```python
class ThemeListView(PermissionRequiredMixin, HtmxTemplateMixin, ListView):
    template_name = "theme/theme_list.html"
    partial_template_name = "theme/partials/theme_table.html"
```

### Successful mutations redirect — even over HTMX

`HtmxRedirectMixin` (`apps/core/mixins.py`): a plain request gets a normal 302; an `HX-Request` gets an `HX-Redirect` response header instead (status 200, empty body). This matters because htmx's default behavior for a 3xx response from its own AJAX call is to follow it *and swap the result into the original target* — correct for a partial update, wrong when the destination is an entirely different page. `HX-Redirect` explicitly tells htmx to do a real `window.location` navigation.

```python
class HtmxRedirectMixin:
    def redirect(self, url: str) -> HttpResponse:
        if self.request.headers.get("HX-Request") == "true":
            return HttpResponse(status=200, headers={"HX-Redirect": url})
        return HttpResponseRedirect(url)
```

### Form validation over HTMX

Invalid form submission via htmx: the view's normal `form_invalid()` flow runs unchanged; `HtmxTemplateMixin` makes it render the partial template (just the form) instead of the full page, at status 200 (htmx swaps any 200 response by default) — the field errors are already in that partial via crispy-forms. No special HTMX-only error branch was written.

### Live search (`?q=`)

`theme/theme_list.html`'s search box:

```html
<input hx-get="{% url 'theme:list' %}" hx-target="#theme-table" hx-swap="outerHTML"
       hx-trigger="input changed delay:300ms from:#id_q, search from:#id_q" ...>
```

`ThemeListView.get_queryset()` reads `?q=` and filters — a two-line addition, not `django-filter` (no other filter dimension exists yet to justify the dependency; see the Phase 02 plan's judgment call #10).

### Global event handling (`static/src/js/htmx/index.js`)

One file, four listeners, registered once:
- `htmx:configRequest` — attaches the CSRF token from Django's `csrftoken` cookie to every htmx request.
- `htmx:beforeRequest` / `htmx:afterRequest` — toggles a `.htmx-request` class on `<html>` driving the `.htmx-indicator` opacity utility (`app.css`).
- `htmx:responseError` / `htmx:sendError` — pushes a message into the shared Alpine `toast` store (never exposes a backend stack trace; just "Request failed (`status`)" / "Network error").
- `htmx:afterSettle` — calls `Alpine.initTree(event.detail.target)` so Alpine directives in newly-swapped content actually initialize (Alpine only auto-scans the DOM once, at `Alpine.start()`).

### `/theme.css` is a plain endpoint, not an htmx target

Deliberately not htmx-driven — it's a `<link rel="stylesheet">`, loaded like any CSS file, versioned via a query string (`?v=<active_version_id>`) so a publish/rollback is picked up by a normal browser cache-invalidation mechanism rather than a client-side swap.
