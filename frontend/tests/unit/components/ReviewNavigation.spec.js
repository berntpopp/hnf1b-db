import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { nextTick } from 'vue';

import AppBar from '@/components/AppBar.vue';
import MobileDrawer from '@/components/MobileDrawer.vue';

const push = vi.fn();
let currentPath = '/';
let authStore;

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
  useRoute: () => ({ path: currentPath }),
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => authStore,
}));

const vuetifyStubs = {
  'v-app-bar': { template: '<header><slot /></header>' },
  'v-container': { template: '<div><slot /></div>' },
  'v-app-bar-nav-icon': {
    template: '<button type="button" @click="$emit(`click`)"><slot /></button>',
  },
  'v-tooltip': { template: '<div><slot name="activator" :props="{}" /><slot /></div>' },
  'v-spacer': { template: '<span />' },
  'v-btn': {
    props: ['to', 'prependIcon', 'ariaLabel'],
    template:
      '<button type="button" :aria-label="ariaLabel" @click="$emit(`click`)"><slot /></button>',
  },
  'v-menu': { template: '<div><slot name="activator" :props="{}" /><slot /></div>' },
  'v-icon': { template: '<i><slot /></i>' },
  'v-list': { template: '<nav><slot /></nav>' },
  'v-list-item': {
    props: ['title', 'to', 'prependIcon', 'ariaLabel'],
    template:
      '<button type="button" :aria-label="ariaLabel" @click="$emit(`click`)"><slot /><span>{{ title }}</span></button>',
  },
  'v-list-item-title': { template: '<span><slot /></span>' },
  'v-list-item-subtitle': { template: '<span><slot /></span>' },
  'v-list-subheader': { template: '<h2><slot /></h2>' },
  'v-divider': { template: '<hr />' },
  'v-chip': { template: '<span><slot /></span>' },
  'v-avatar': { template: '<span><slot /></span>' },
  'v-navigation-drawer': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<aside><slot /></aside>',
  },
  'v-img': { template: '<button type="button" @click="$emit(`click`)" />' },
  ThemeSwitcher: { template: '<button type="button" aria-label="Theme" />' },
};

const mountWithStubs = (component, options = {}) =>
  mount(component, {
    ...options,
    global: {
      stubs: vuetifyStubs,
      ...(options.global || {}),
    },
  });

describe('review navigation', () => {
  beforeEach(() => {
    push.mockClear();
    currentPath = '/';
    authStore = {
      isAuthenticated: true,
      user: { username: 'curator', role: 'curator' },
      logout: vi.fn(),
    };
  });

  it('shows review queue navigation to desktop curators', () => {
    const wrapper = mountWithStubs(AppBar);

    expect(wrapper.text()).toContain('Review Queue');
  });

  it('shows review queue navigation to desktop admins', () => {
    authStore.user = { username: 'admin', role: 'admin' };

    const wrapper = mountWithStubs(AppBar);

    expect(wrapper.text()).toContain('Review Queue');
  });

  it('hides review queue navigation from desktop viewers', () => {
    authStore.user = { username: 'viewer', role: 'viewer' };

    const wrapper = mountWithStubs(AppBar);

    expect(wrapper.text()).not.toContain('Review Queue');
  });

  it('shows review queue navigation in the mobile drawer for curators', () => {
    const wrapper = mountWithStubs(MobileDrawer, { props: { modelValue: true } });

    expect(wrapper.text()).toContain('Review Queue');
  });

  it('shows review queue navigation in the mobile drawer for admins', () => {
    authStore.user = { username: 'admin', role: 'admin' };

    const wrapper = mountWithStubs(MobileDrawer, { props: { modelValue: true } });

    expect(wrapper.text()).toContain('Review Queue');
  });

  it('hides review queue navigation from mobile viewers', () => {
    authStore.user = { username: 'viewer', role: 'viewer' };

    const wrapper = mountWithStubs(MobileDrawer, { props: { modelValue: true } });

    expect(wrapper.text()).not.toContain('Review Queue');
  });

  it('closes the drawer when a curator opens the review queue', async () => {
    const wrapper = mountWithStubs(MobileDrawer, { props: { modelValue: true } });

    await wrapper.get('[aria-label="Open review queue"]').trigger('click');
    await nextTick();

    expect(wrapper.emitted('update:modelValue')).toContainEqual([false]);
  });
});
