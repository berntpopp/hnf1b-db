/**
 * Import-time polyfills that must be installed before any other test setup
 * module (notably the Vuetify plugin) is evaluated.
 *
 * Vuetify's `util/globals` reads `CSS.supports()` at import time. happy-dom
 * (the default Vitest environment) exposes a `CSS` global, but jsdom — used by
 * the DOMPurify sanitization suites via `@vitest-environment jsdom` — does not.
 * Without this shim those files throw "CSS is not defined" the moment
 * tests/setup.js imports the Vuetify plugin. Guarded so it is a no-op under
 * happy-dom and in real browsers.
 */
if (!globalThis.CSS) {
  globalThis.CSS = {
    supports: () => false,
    escape: (value) => String(value),
  };
}
