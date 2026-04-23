/**
 * Global test setup for Vitest
 *
 * Based on agde-frontend proven patterns
 * Reference: /mnt/c/development/agde-frontend/tests/setup.js
 */

import { config } from '@vue/test-utils';
import vuetify from '@/plugins/vuetify';

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

// Register Vuetify plugin globally for all tests
config.global.plugins = [vuetify];
