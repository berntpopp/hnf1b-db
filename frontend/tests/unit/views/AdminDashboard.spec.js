/**
 * Characterization test for AdminDashboard.vue.
 *
 * Tests observable sections (sync cards, status display, buttons)
 * without exercising the polling mechanism itself (that becomes
 * useSyncTask in Wave 5 and gets its own unit tests).
 */
import { describe, it, expect, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

// AdminDashboard imports the API module as a namespace (`import * as API from '@/api'`)
// so we mock the exact functions it calls. The observable mount path needs:
//   - getAdminStatus  (fetched on mount via Promise.all)
//   - getAdminStatistics (fetched on mount via Promise.all)
// Everything else is only touched by user actions or the polling loop,
// which this characterization test deliberately does not exercise.
vi.mock('@/api', () => ({
  getAdminStatus: vi.fn().mockResolvedValue({
    data: {
      database: { status: 'healthy', phenopacket_count: 864 },
      redis: { status: 'healthy' },
      vep: { status: 'healthy' },
      sync_status: [],
    },
  }),
  getAdminStatistics: vi.fn().mockResolvedValue({
    data: {
      phenopackets: { total: 864, with_variants: 500 },
      publications: { cached: 120, referenced: 130 },
      variants: { cached: 200 },
    },
  }),
  startPublicationSync: vi.fn().mockResolvedValue({ data: { task_id: 'pub-1' } }),
  getPublicationSyncStatus: vi.fn().mockResolvedValue({ data: { status: 'idle' } }),
  startVariantSync: vi.fn().mockResolvedValue({ data: { task_id: 'var-1' } }),
  getVariantSyncStatus: vi.fn().mockResolvedValue({ data: { status: 'idle' } }),
  startReferenceInit: vi.fn().mockResolvedValue({ data: { status: 'ok' } }),
  startGenesSync: vi.fn().mockResolvedValue({ data: { task_id: 'genes-1' } }),
  getGenesSyncStatus: vi.fn().mockResolvedValue({ data: { status: 'idle' } }),
  getReferenceDataStatus: vi.fn().mockResolvedValue({ data: {} }),
}));

// Polyfill ResizeObserver (happy-dom doesn't ship it and Vuetify needs it).
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// The app uses window.logService (see AGENTS.md: no console.log in frontend).
globalThis.window.logService = {
  debug: vi.fn(),
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
};

async function mountDashboard() {
  const vuetify = createVuetify({ components, directives });
  const AdminDashboard = (await import('@/views/AdminDashboard.vue')).default;
  return mount(AdminDashboard, {
    global: { plugins: [vuetify] },
  });
}

describe('AdminDashboard.vue (characterization)', () => {
  it('mounts without throwing', async () => {
    const wrapper = await mountDashboard();
    await flushPromises();
    expect(wrapper.exists()).toBe(true);
  });

  it('renders the sync operations section', async () => {
    const wrapper = await mountDashboard();
    await flushPromises();
    const text = wrapper.text().toLowerCase();
    expect(text).toContain('sync');
  });

  it('renders at least 4 action buttons (the 4 sync operations)', async () => {
    const wrapper = await mountDashboard();
    await flushPromises();
    const buttons = wrapper.findAll('button');
    expect(buttons.length).toBeGreaterThanOrEqual(4);
  });

  it('calls getAdminStatus on mount', async () => {
    const api = await import('@/api');
    await mountDashboard();
    await flushPromises();
    expect(api.getAdminStatus).toHaveBeenCalled();
  });
});
