/**
 * Theme Studio live preview — Alpine.js updates scoped CSS variables on the
 * preview pane only (never :root) as the admin edits, with zero writes to
 * the server until "Save draft" is submitted (Phase 02 plan §21).
 *
 * Uses event delegation (a single @input listener on the container) reading
 * data-preview-* attributes set on each field in apps/theme/forms.py,
 * rather than x-model on every field — crispy-forms renders the actual
 * <input> elements, so this avoids needing a custom widget just to attach
 * Alpine bindings.
 */

const COLOR_VAR_MAP = {
  brand: "--color-brand",
  brand_hover: "--color-brand-hover",
  brand_secondary: "--color-brand-secondary",
  brand_accent: "--color-brand-accent",
  background: "--color-background",
  surface: "--color-surface",
  text_primary: "--color-primary",
  text_secondary: "--color-secondary",
  border_default: "--color-default",
  success: "--color-success",
  warning: "--color-warning",
  danger: "--color-danger",
  info: "--color-info",
};

const RADIUS_VAR_MAP = { sm: "--radius-sm", md: "--radius-md", lg: "--radius-lg" };

document.addEventListener("alpine:init", () => {
  Alpine.data("themeStudio", () => ({
    previewMode: "light",

    init() {
      this.$nextTick(() => this.applyAll());
    },

    setPreviewMode(mode) {
      this.previewMode = mode;
      this.applyAll();
    },

    onFieldInput(event) {
      this.applyField(event.target);
    },

    applyAll() {
      this.$root.querySelectorAll(
        "[data-preview-color], [data-preview-radius], [data-preview-typography]"
      ).forEach((el) => this.applyField(el));
    },

    applyField(el) {
      const preview = this.$refs.preview;
      if (!preview || !el.value) return;

      if (el.dataset.previewColor) {
        if (el.dataset.previewMode !== this.previewMode) return;
        const varName = COLOR_VAR_MAP[el.dataset.previewColor];
        if (varName) preview.style.setProperty(varName, el.value);
      } else if (el.dataset.previewRadius) {
        const varName = RADIUS_VAR_MAP[el.dataset.previewRadius];
        if (varName) preview.style.setProperty(varName, el.value);
      } else if (el.dataset.previewTypography === "font_family") {
        preview.style.setProperty("--font-sans", el.value);
      } else if (el.dataset.previewTypography === "font_size_base") {
        preview.style.setProperty("--font-size-base", el.value);
      }
    },
  }));
});
