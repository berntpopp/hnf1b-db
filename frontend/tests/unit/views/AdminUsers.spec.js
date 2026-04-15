/**
 * Characterization test for AdminUsers.vue.
 *
 * Wave 5b Task 14: verifies the view mounts, loads users, and
 * filters the _system_migration_ placeholder from the rendered list.
 */
import { describe, it, expect, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

vi.mock('@/api', () => ({
  listUsers: vi.fn(async () => ({
    data: [
      {
        id: 1,
        username: 'admin',
        email: 'a@example.com',
        full_name: 'Admin',
        role: 'admin',
        is_active: true,
        locked_until: null,
      },
      {
        id: 2,
        username: 'curator',
        email: 'c@example.com',
        full_name: 'Curator',
        role: 'curator',
        is_active: true,
        locked_until: null,
      },
      {
        id: 3,
        username: '_system_migration_',
        email: 's@example.com',
        full_name: 'System',
        role: 'viewer',
        is_active: false,
        locked_until: null,
      },
    ],
  })),
  deleteUser: vi.fn(),
  unlockUser: vi.fn(),
  createUser: vi.fn(),
  updateUser: vi.fn(),
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

async function mountAdminUsers() {
  const vuetify = createVuetify({ components, directives });
  const AdminUsers = (await import('@/views/AdminUsers.vue')).default;
  return mount(AdminUsers, {
    global: {
      plugins: [vuetify],
      stubs: {
        RouterLink: true,
      },
    },
  });
}

describe('AdminUsers.vue (characterization)', () => {
  it('mounts without throwing', async () => {
    const wrapper = await mountAdminUsers();
    await flushPromises();
    expect(wrapper.exists()).toBe(true);
  });

  it('renders users excluding _system_migration_', async () => {
    const wrapper = await mountAdminUsers();
    await flushPromises();
    const text = wrapper.text();
    expect(text).toContain('admin');
    expect(text).toContain('curator');
    expect(text).not.toContain('_system_migration_');
  });

  it('calls listUsers on mount', async () => {
    const api = await import('@/api');
    await mountAdminUsers();
    await flushPromises();
    expect(api.listUsers).toHaveBeenCalled();
  });

  it('renders create user button', async () => {
    const wrapper = await mountAdminUsers();
    await flushPromises();
    const text = wrapper.text();
    expect(text).toContain('Create User');
  });
});
