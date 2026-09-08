/**
 * Global JS entry point.
 *
 * There is no bundler here on purpose (see docs/architecture/
 * frontend-architecture.md) — this file, alpine/index.js and htmx/index.js
 * are loaded as plain <script> tags in that exact order, followed last by
 * the vendored htmx/alpine builds (alpine.min.js with `defer`, per Alpine's
 * documented init order). Keep this file small; most behavior belongs in
 * alpine/index.js or htmx/index.js.
 */

document.documentElement.classList.remove("no-js");
document.documentElement.classList.add("js");

window.addEventListener("error", (event) => {
  console.error("[ems] uncaught error:", event.error ?? event.message);
});
