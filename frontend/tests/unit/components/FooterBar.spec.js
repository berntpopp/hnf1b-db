import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import { createPinia } from 'pinia';
import { defineComponent, h } from 'vue';

import FooterBar from '@/components/FooterBar.vue';

// Stub the healthService so the component does not attempt real HTTP polling.
vi.mock('@/services/healthService', () => ({
  healthService: {
    subscribe: vi.fn(() => () => {}),
    getStatus: vi.fn(() => ({
      backend: {
        connected: false,
        version: null,
        responseTime: null,
        lastCheck: null,
        error: null,
      },
    })),
    checkBackendHealth: vi.fn(),
  },
}));

function mockFetchConfig(config) {
  global.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve(config) }));
}

// Helpers for temporarily overriding import.meta.env flags.
function withEnv(overrides, fn) {
  const prev = {};
  for (const k of Object.keys(overrides)) {
    prev[k] = import.meta.env[k];
    import.meta.env[k] = overrides[k];
  }
  try {
    return fn();
  } finally {
    for (const k of Object.keys(overrides)) {
      import.meta.env[k] = prev[k];
    }
  }
}

/**
 * VFooter with `app` prop requires a Vuetify layout context provided by
 * v-app / VApp. Wrap FooterBar in a minimal VApp shell so the layout
 * injection is satisfied.
 */
function makeAppWrapper() {
  return defineComponent({
    name: 'AppWrapper',
    components: { FooterBar },
    render() {
      return h(components.VApp, null, {
        default: () => h(FooterBar),
      });
    },
  });
}

describe('FooterBar API docs link (M10)', () => {
  let vuetify;
  let pinia;

  beforeEach(() => {
    vuetify = createVuetify({ components, directives });
    pinia = createPinia();
    window.logService = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('omits the API docs link when VITE_API_URL is unset in prod build', async () => {
    await withEnv({ PROD: true, VITE_API_URL: '' }, async () => {
      mockFetchConfig([
        { enabled: true, id: 'api', label: 'API', url: '__API_DOCS_URL__' },
        { enabled: true, id: 'gh', label: 'GitHub', url: 'https://github.com/x/y' },
      ]);
      const wrapper = mount(makeAppWrapper(), {
        global: { plugins: [vuetify, pinia] },
      });
      await new Promise((r) => setTimeout(r, 20));
      const hrefs = wrapper.findAll('a').map((a) => a.attributes('href') || '');
      expect(hrefs).not.toContain('http://localhost:8000/api/v2/docs');
      expect(hrefs.some((h) => h.includes('github.com'))).toBe(true);
      expect(window.logService.warn).toHaveBeenCalledWith(
        expect.stringContaining('API docs URL not configured'),
        expect.anything()
      );
    });
  });

  it('includes the API docs link when VITE_API_URL is set', async () => {
    await withEnv({ PROD: true, VITE_API_URL: 'https://api.example.com/api/v2' }, async () => {
      mockFetchConfig([{ enabled: true, id: 'api', label: 'API', url: '__API_DOCS_URL__' }]);
      const wrapper = mount(makeAppWrapper(), {
        global: { plugins: [vuetify, pinia] },
      });
      await new Promise((r) => setTimeout(r, 20));
      const hrefs = wrapper.findAll('a').map((a) => a.attributes('href') || '');
      expect(hrefs).toContain('https://api.example.com/api/v2/docs');
    });
  });

  it('falls back to localhost in dev when VITE_API_URL is unset', async () => {
    await withEnv({ PROD: false, VITE_API_URL: '' }, async () => {
      mockFetchConfig([{ enabled: true, id: 'api', label: 'API', url: '__API_DOCS_URL__' }]);
      const wrapper = mount(makeAppWrapper(), {
        global: { plugins: [vuetify, pinia] },
      });
      await new Promise((r) => setTimeout(r, 20));
      const hrefs = wrapper.findAll('a').map((a) => a.attributes('href') || '');
      expect(hrefs).toContain('http://localhost:8000/api/v2/docs');
    });
  });
});
