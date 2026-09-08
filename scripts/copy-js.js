/**
 * Copies our hand-written JS and the vendored Alpine/htmx builds into
 * static/dist/js/, which is the only directory Django's STATICFILES_DIRS
 * points to (static/src and static/vendor are source, never served
 * directly). No bundler is used on purpose — see
 * docs/architecture/frontend-architecture.md.
 */
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const destJs = path.join(root, "static", "dist", "js");

fs.rmSync(destJs, { recursive: true, force: true });
fs.mkdirSync(destJs, { recursive: true });

fs.cpSync(path.join(root, "static", "src", "js"), destJs, { recursive: true });
fs.cpSync(
  path.join(root, "static", "vendor", "js"),
  path.join(destJs, "vendor"),
  { recursive: true }
);

console.log("Copied JS to static/dist/js/");
