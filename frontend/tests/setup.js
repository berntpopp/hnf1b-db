/**
 * Global test setup for Vitest
 *
 * Based on agde-frontend proven patterns
 * Reference: /mnt/c/development/agde-frontend/tests/setup.js
 */

import { config } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

// Polyfill ResizeObserver for Vuetify components
// happy-dom doesn't include ResizeObserver by default
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Polyfill visualViewport for Vuetify VOverlay (v-dialog, v-menu) positioning.
// happy-dom doesn't expose window.visualViewport; without it Vuetify's
// locationStrategies watcher throws "visualViewport is not defined" when any
// overlay-based component mounts with modelValue=true.
if (!globalThis.visualViewport) {
  globalThis.visualViewport = {
    width: 1024,
    height: 768,
    offsetTop: 0,
    offsetLeft: 0,
    scale: 1,
    addEventListener: () => {},
    removeEventListener: () => {},
  };
}

// Create Vuetify instance for tests
// CRITICAL: Without this, Vuetify components will crash with
// "Error: [Vuetify] Could not find defaults instance"
const vuetify = createVuetify({
  components,
  directives,
});

// Register Vuetify plugin globally for all tests
config.global.plugins = [vuetify];
