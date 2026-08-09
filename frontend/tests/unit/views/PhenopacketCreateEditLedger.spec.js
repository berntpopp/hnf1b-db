import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { apiGet, getPhenopacket } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  getPhenopacket: vi.fn(),
}));

vi.mock('@/api', () => ({
  getPhenopacket,
  createPhenopacket: vi.fn(),
  updatePhenopacket: vi.fn(),
  apiClient: { get: apiGet },
}));
vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ user: { username: 'admin', full_name: 'Admin User', role: 'admin' } }),
}));
vi.mock('@/components/curation/reports/ReportObservationWorkspace.vue', () => ({
  default: {
    name: 'ReportObservationWorkspace',
    props: ['phenopacketId', 'recordState', 'userRole'],
    emits: ['available', 'unavailable', 'dirty-change'],
    template: '<div data-testid="ledger-workspace">Ledger workspace</div>',
  },
}));

import PhenopacketCreateEdit from '@/views/PhenopacketCreateEdit.vue';

const response = {
  phenopacket: {
    id: 'PP-317',
    subject: { id: '317', sex: 'UNKNOWN_SEX' },
    phenotypicFeatures: [],
    interpretations: [],
    metaData: { externalReferences: [] },
  },
  revision: 7,
  state: 'draft',
};

function mountView() {
  return mount(PhenopacketCreateEdit, {
    global: {
      mocks: {
        $route: { params: { phenopacket_id: 'PP-317' } },
        $router: { push: vi.fn() },
      },
      stubs: {
        VContainer: { template: '<div><slot /></div>' },
        VCard: { template: '<div><slot /></div>' },
        VCardText: { template: '<div><slot /></div>' },
        VProgressCircular: true,
        VAlert: { template: '<div><slot /></div>' },
        VIcon: true,
        VForm: { template: '<form><slot /></form>' },
      },
    },
  });
}

describe('PhenopacketCreateEdit observation-ledger integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiGet.mockResolvedValue({ data: { data: [] } });
    getPhenopacket.mockResolvedValue({ data: response });
    window.logService = { info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn() };
  });

  it('mounts the report workspace for an individual edit route before exposing legacy mutation', async () => {
    const wrapper = mountView();
    await flushPromises();
    const workspace = wrapper.findComponent({ name: 'ReportObservationWorkspace' });
    expect(workspace.exists()).toBe(true);
    expect(workspace.props()).toMatchObject({
      phenopacketId: 'PP-317',
      recordState: 'draft',
      userRole: 'admin',
    });
    expect(wrapper.find('form').exists()).toBe(false);
  });

  it('does not block the observation ledger when legacy-only vocabularies fail', async () => {
    apiGet.mockRejectedValue(new Error('legacy vocabulary offline'));
    const wrapper = mountView();
    await flushPromises();
    expect(wrapper.findComponent({ name: 'ReportObservationWorkspace' }).exists()).toBe(true);
    expect(wrapper.text()).not.toContain('Failed to load form vocabularies');
  });

  it('falls back to the legacy form only when the ledger API explicitly reports unavailable', async () => {
    const wrapper = mountView();
    await flushPromises();
    await wrapper.findComponent({ name: 'ReportObservationWorkspace' }).vm.$emit('unavailable');
    await wrapper.vm.$nextTick();
    expect(wrapper.find('[data-testid="ledger-workspace"]').exists()).toBe(false);
    expect(wrapper.find('form').exists()).toBe(true);
  });

  it('includes ledger dirty state in the route-leave guard without window.confirm', async () => {
    const wrapper = mountView();
    await flushPromises();
    await wrapper
      .findComponent({ name: 'ReportObservationWorkspace' })
      .vm.$emit('dirty-change', true);
    const next = vi.fn();
    PhenopacketCreateEdit.beforeRouteLeave.call(wrapper.vm, {}, {}, next);
    expect(next).not.toHaveBeenCalled();
    expect(wrapper.vm.showUnsavedDialog).toBe(true);
  });
});
