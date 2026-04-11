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
            props: ['loading'],
            template: '<button @click="$emit(\'click\')"><slot /></button>',
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

  it('calls authStore.devLoginAs when a button is clicked', async () => {
    const authStore = useAuthStore();
    const buttons = wrapper.findAll('button');
    await buttons[0].trigger('click');
    expect(authStore.devLoginAs).toHaveBeenCalled();
  });
});
