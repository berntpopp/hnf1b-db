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

// Mock vue-router — the component uses useRouter().push and useRoute().query.
const pushSpy = vi.fn();
const routeRef = { query: {} };
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushSpy }),
  useRoute: () => routeRef,
}));

// Mock window.logService (used in onClick error handler)
globalThis.window = globalThis.window || {};
globalThis.window.logService = {
  info: vi.fn(),
  error: vi.fn(),
  warn: vi.fn(),
  debug: vi.fn(),
};

function mountComponent() {
  return mount(DevQuickLogin, {
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
}

describe('DevQuickLogin', () => {
  let wrapper;

  beforeEach(() => {
    vi.clearAllMocks();
    pushSpy.mockReset();
    routeRef.query = {};

    wrapper = mountComponent();
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
    authStore.devLoginAs.mockResolvedValue(undefined);
    const buttons = wrapper.findAll('button');

    // First button corresponds to fixtureUsers[0] = dev-admin.
    await buttons[0].trigger('click');
    await vi.waitFor(() => expect(authStore.devLoginAs).toHaveBeenCalledTimes(1));
    expect(authStore.devLoginAs).toHaveBeenCalledWith('dev-admin');

    // Second button → dev-curator.
    await buttons[1].trigger('click');
    await vi.waitFor(() => expect(authStore.devLoginAs).toHaveBeenCalledTimes(2));
    expect(authStore.devLoginAs).toHaveBeenLastCalledWith('dev-curator');

    // Third button → dev-viewer.
    await buttons[2].trigger('click');
    await vi.waitFor(() => expect(authStore.devLoginAs).toHaveBeenCalledTimes(3));
    expect(authStore.devLoginAs).toHaveBeenLastCalledWith('dev-viewer');
  });

  it('navigates to /user by default after a successful login', async () => {
    const authStore = useAuthStore();
    authStore.devLoginAs.mockResolvedValue(undefined);
    const buttons = wrapper.findAll('button');

    await buttons[0].trigger('click');
    await vi.waitFor(() => expect(pushSpy).toHaveBeenCalledTimes(1));
    expect(pushSpy).toHaveBeenCalledWith('/user');
  });

  it('honours a safe ?redirect= query on login', async () => {
    routeRef.query = { redirect: '/phenopackets/create' };
    wrapper.unmount();
    wrapper = mountComponent();

    const authStore = useAuthStore();
    authStore.devLoginAs.mockResolvedValue(undefined);
    const buttons = wrapper.findAll('button');

    await buttons[0].trigger('click');
    await vi.waitFor(() => expect(pushSpy).toHaveBeenCalledTimes(1));
    expect(pushSpy).toHaveBeenCalledWith('/phenopackets/create');
  });

  it('rejects an absolute-URL redirect and falls back to /user', async () => {
    routeRef.query = { redirect: 'https://evil.example.com/steal' };
    wrapper.unmount();
    wrapper = mountComponent();

    const authStore = useAuthStore();
    authStore.devLoginAs.mockResolvedValue(undefined);
    const buttons = wrapper.findAll('button');

    await buttons[0].trigger('click');
    await vi.waitFor(() => expect(pushSpy).toHaveBeenCalledTimes(1));
    expect(pushSpy).toHaveBeenCalledWith('/user');
  });

  it('rejects a protocol-relative redirect and falls back to /user', async () => {
    routeRef.query = { redirect: '//evil.example.com/steal' };
    wrapper.unmount();
    wrapper = mountComponent();

    const authStore = useAuthStore();
    authStore.devLoginAs.mockResolvedValue(undefined);
    const buttons = wrapper.findAll('button');

    await buttons[0].trigger('click');
    await vi.waitFor(() => expect(pushSpy).toHaveBeenCalledTimes(1));
    expect(pushSpy).toHaveBeenCalledWith('/user');
  });

  it('rejects a redirect back to /login (never land on an auth page)', async () => {
    routeRef.query = { redirect: '/login' };
    wrapper.unmount();
    wrapper = mountComponent();

    const authStore = useAuthStore();
    authStore.devLoginAs.mockResolvedValue(undefined);
    const buttons = wrapper.findAll('button');

    await buttons[0].trigger('click');
    await vi.waitFor(() => expect(pushSpy).toHaveBeenCalledTimes(1));
    expect(pushSpy).toHaveBeenCalledWith('/user');
  });

  it('does not navigate when devLoginAs throws', async () => {
    const authStore = useAuthStore();
    authStore.devLoginAs.mockRejectedValue(new Error('401'));
    const buttons = wrapper.findAll('button');

    await buttons[0].trigger('click');
    await vi.waitFor(() =>
      expect(window.logService.error).toHaveBeenCalledWith(
        'dev login failed',
        expect.objectContaining({ username: 'dev-admin' })
      )
    );
    expect(pushSpy).not.toHaveBeenCalled();
  });
});
