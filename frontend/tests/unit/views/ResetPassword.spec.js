import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

vi.mock('@/api', () => ({
  confirmPasswordReset: vi.fn().mockResolvedValue({ data: { message: 'ok' } }),
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { token: 'test-token-123' } }),
  useRouter: () => ({ push: vi.fn() }),
}));

// Polyfill ResizeObserver (happy-dom doesn't ship it and Vuetify needs it).
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// The app uses window.logService (see CLAUDE.md: no console.log in frontend).
globalThis.window.logService = {
  debug: vi.fn(),
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
};

async function mountComponent() {
  const vuetify = createVuetify({ components, directives });
  const ResetPassword = (await import('@/views/ResetPassword.vue')).default;
  return mount(ResetPassword, {
    global: {
      plugins: [vuetify],
      stubs: {
        RouterLink: {
          template: '<a><slot /></a>',
        },
      },
    },
  });
}

describe('ResetPassword', () => {
  it('renders password inputs', async () => {
    const wrapper = await mountComponent();
    const inputs = wrapper.findAll('input[type="password"]');
    expect(inputs.length).toBe(2);
  });

  it('shows request new link', async () => {
    const wrapper = await mountComponent();
    expect(wrapper.text()).toContain('Request a new reset link');
  });
});
