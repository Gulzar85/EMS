/**
 * Alpine.js component registration.
 *
 * Must run BEFORE the vendored alpine.min.js executes (that script is loaded
 * with `defer`, per Alpine's documented initialization order) — this file
 * registers components on the `alpine:init` event, which Alpine fires right
 * before it scans the DOM.
 *
 * Alpine here is strictly client-side UI state (sidebar open/collapsed,
 * dropdown open/closed, toast visibility) — it never becomes a source of
 * truth for server data. See docs/architecture/frontend-architecture.md.
 */

document.addEventListener("alpine:init", () => {
  Alpine.data("appShell", () => ({
    mobileSidebarOpen: false,
    sidebarCollapsed: false,

    toggleMobileSidebar() {
      this.mobileSidebarOpen = !this.mobileSidebarOpen;
    },
    toggleSidebarCollapsed() {
      this.sidebarCollapsed = !this.sidebarCollapsed;
    },
  }));

  Alpine.data("dropdown", () => ({
    open: false,
    toggle() {
      this.open = !this.open;
    },
    close() {
      this.open = false;
    },
  }));

  Alpine.store("toast", {
    items: [],
    nextId: 1,
    push(variant, message) {
      const id = this.nextId++;
      this.items.push({ id, variant, message });
      setTimeout(() => this.dismiss(id), 5000);
    },
    dismiss(id) {
      this.items = this.items.filter((item) => item.id !== id);
    },
  });

  window.addEventListener("toast", (event) => {
    Alpine.store("toast").push(event.detail.variant, event.detail.message);
  });
});
