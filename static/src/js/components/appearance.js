/**
 * Appearance (light/dark/system) switcher — registered on alpine:init like
 * every other component (see static/src/js/alpine/index.js).
 *
 * Deliberately plain fetch(), not htmx: there is no HTML to swap here, only
 * a background persistence call after Alpine has already applied the
 * change to the DOM optimistically. The server remains the source of truth
 * for the *next* page load (see apps/theme/context_processors.py).
 */

function getCsrfToken() {
  const match = document.cookie.match(/(^| )csrftoken=([^;]+)/);
  return match ? match[2] : "";
}

document.addEventListener("alpine:init", () => {
  Alpine.data("appearanceSwitcher", (initial) => ({
    current: initial,

    setAppearance(value) {
      this.current = value;
      if (value === "system") {
        delete document.documentElement.dataset.theme;
      } else {
        document.documentElement.dataset.theme = value;
      }
      fetch("/preferences/appearance/", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "X-CSRFToken": getCsrfToken(),
        },
        body: `appearance=${value}`,
      });
    },
  }));
});
