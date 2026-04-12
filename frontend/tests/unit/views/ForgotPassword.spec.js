import { describe, it, expect, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

vi.mock('@/api', () => ({
  requestPasswordReset: vi.fn().mockResolvedValue({ data: { message: 'sent' } }),
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
  const ForgotPassword = (await import('@/views/ForgotPassword.vue')).default;
  return mount(ForgotPassword, {
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

describe('ForgotPassword', () => {
  it('renders email input', async () => {
    const wrapper = await mountComponent();
    expect(wrapper.find('input[type="email"]').exists()).toBe(true);
  });

  it('shows confirmation after submit', async () => {
    const wrapper = await mountComponent();
    const input = wrapper.find('input[type="email"]');
    await input.setValue('test@example.com');
    await wrapper.find('form').trigger('submit.prevent');
    await flushPromises();
    expect(wrapper.text()).toContain('If an account exists');
  });

  it('shows back to login link', async () => {
    const wrapper = await mountComponent();
    expect(wrapper.text()).toContain('Back to Login');
  });
});
