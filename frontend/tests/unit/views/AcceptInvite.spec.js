import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import AcceptInvite from '@/views/AcceptInvite.vue';

// ResizeObserver polyfill for happy-dom
globalThis.ResizeObserver =
  globalThis.ResizeObserver ||
  class {
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

vi.mock('@/api', () => ({
  acceptInvite: vi.fn().mockResolvedValue({ data: { username: 'newuser' } }),
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { token: 'invite-token' }, query: { email: 'test@example.com' } }),
  useRouter: () => ({ push: vi.fn() }),
}));

const vuetify = createVuetify({ components, directives });

function mountComponent() {
  return mount(AcceptInvite, {
    global: {
      plugins: [vuetify],
      stubs: { RouterLink: { template: '<a><slot /></a>' } },
    },
  });
}

describe('AcceptInvite', () => {
  it('renders username and password inputs', () => {
    const wrapper = mountComponent();
    const inputs = wrapper.findAll('input');
    expect(inputs.length).toBeGreaterThanOrEqual(3);
  });

  it('shows invite email from query param', () => {
    const wrapper = mountComponent();
    expect(wrapper.text()).toContain('test@example.com');
  });

  it('renders create account button', () => {
    const wrapper = mountComponent();
    expect(wrapper.text()).toContain('Create Account');
  });
});
