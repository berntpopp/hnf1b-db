/**
 * Unit tests for DevQuickLogin.vue
 *
 * Wave 5a Layer 4 — dev-mode quick-login panel.
 * The component renders three fixture-user buttons and delegates
 * to authStore.devLoginAs on click.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { createTestingPinia } from '@pinia/testing';
import DevQuickLogin from '@/components/auth/DevQuickLogin.vue';
import { useAuthStore } from '@/stores/authStore';

// Mock window.logService (used in onClick error handler)
globalThis.window = globalThis.window || {};
globalThis.window.logService = {
  info: vi.fn(),
  error: vi.fn(),
  warn: vi.fn(),
  debug: vi.fn(),
};

describe('DevQuickLogin', () => {
  let wrapper;

  beforeEach(() => {
    vi.clearAllMocks();

    wrapper = mount(DevQuickLogin, {
      global: {
        plugins: [createTestingPinia({ createSpy: vi.fn })],
        stubs: {
          'v-card': { template: '<div><slot /></div>' },
          'v-card-title': { template: '<div><slot /></div>' },
          'v-card-text': { template: '<div><slot /></div>' },
          'v-btn': {
            // Explicit `emits` declaration prevents Vue from double-firing
            // the parent's @click listener (once via custom emit, once via
            // native-click fallthrough). Without this the test would see
            // `devLoginAs` called twice per stub click.
            props: ['loading'],
            emits: ['click'],
            template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
          },
        },
      },
    });
  });

  it('renders three fixture user buttons', () => {
    const buttons = wrapper.findAll('button');
    expect(buttons.length).toBe(3);
    const labels = buttons.map((b) => b.text());
    expect(labels.some((l) => l.includes('admin'))).toBe(true);
    expect(labels.some((l) => l.includes('curator'))).toBe(true);
    expect(labels.some((l) => l.includes('viewer'))).toBe(true);
  });

  it('calls authStore.devLoginAs with the clicked fixture username', async () => {
    const authStore = useAuthStore();
    const buttons = wrapper.findAll('button');

    // First button corresponds to fixtureUsers[0] = dev-admin.
    await buttons[0].trigger('click');
    expect(authStore.devLoginAs).toHaveBeenCalledTimes(1);
    expect(authStore.devLoginAs).toHaveBeenCalledWith('dev-admin');

    // Second button → dev-curator.
    await buttons[1].trigger('click');
    expect(authStore.devLoginAs).toHaveBeenCalledTimes(2);
    expect(authStore.devLoginAs).toHaveBeenLastCalledWith('dev-curator');

    // Third button → dev-viewer.
    await buttons[2].trigger('click');
    expect(authStore.devLoginAs).toHaveBeenCalledTimes(3);
    expect(authStore.devLoginAs).toHaveBeenLastCalledWith('dev-viewer');
  });
});
