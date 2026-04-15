import { describe, it, expect, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import VerifyEmail from '@/views/VerifyEmail.vue';

globalThis.ResizeObserver =
  globalThis.ResizeObserver ||
  class {
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

const mockVerifyEmail = vi.fn();

vi.mock('@/api', () => ({
  verifyEmail: (...args) => mockVerifyEmail(...args),
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { token: 'verify-token-123' } }),
}));

const vuetify = createVuetify({ components, directives });

function mountComponent() {
  return mount(VerifyEmail, {
    global: {
      plugins: [vuetify],
      stubs: { RouterLink: { template: '<a><slot /></a>' } },
    },
  });
}

describe('VerifyEmail', () => {
  it('auto-consumes token on mount and shows success', async () => {
    mockVerifyEmail.mockResolvedValueOnce({ data: { message: 'ok' } });
    const wrapper = mountComponent();
    await flushPromises();
    expect(mockVerifyEmail).toHaveBeenCalledWith('verify-token-123');
    expect(wrapper.text()).toContain('verified successfully');
  });

  it('shows error for invalid token', async () => {
    mockVerifyEmail.mockRejectedValueOnce({
      response: { data: { detail: 'Token expired' } },
    });
    const wrapper = mountComponent();
    await flushPromises();
    expect(wrapper.text()).toContain('Token expired');
  });
});
