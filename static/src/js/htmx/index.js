/**
 * htmx conventions for this project (see docs/architecture/frontend-architecture.md):
 *  - CSRF token attached to every htmx request from Django's csrftoken cookie.
 *  - A page-level loading indicator toggled on beforeRequest/afterRequest.
 *  - Errors surfaced as a toast via the shared Alpine "toast" store, never a
 *    silent failure.
 *  - Newly-swapped content re-scanned by Alpine (Alpine only auto-initializes
 *    what exists at Alpine.start() time).
 */

function getCookie(name) {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? decodeURIComponent(match[2]) : null;
}

document.body.addEventListener("htmx:configRequest", (event) => {
  event.detail.headers["X-CSRFToken"] = getCookie("csrftoken");
});

document.body.addEventListener("htmx:beforeRequest", () => {
  document.documentElement.classList.add("htmx-request");
});

document.body.addEventListener("htmx:afterRequest", () => {
  document.documentElement.classList.remove("htmx-request");
});

document.body.addEventListener("htmx:responseError", (event) => {
  window.dispatchEvent(
    new CustomEvent("toast", {
      detail: {
        variant: "danger",
        message: `Request failed (${event.detail.xhr.status}). Please try again.`,
      },
    })
  );
});

document.body.addEventListener("htmx:sendError", () => {
  window.dispatchEvent(
    new CustomEvent("toast", {
      detail: { variant: "danger", message: "Network error — please check your connection." },
    })
  );
});

document.body.addEventListener("htmx:afterSettle", (event) => {
  if (window.Alpine) {
    window.Alpine.initTree(event.detail.target);
  }
});
