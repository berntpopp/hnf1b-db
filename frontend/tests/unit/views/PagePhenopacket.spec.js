import { flushPromises, shallowMount } from '@vue/test-utils';
import { nextTick, reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PagePhenopacket from '@/views/PagePhenopacket.vue';

vi.mock('@/api', () => ({
  getPhenopacket: vi.fn(),
  deletePhenopacket: vi.fn(),
  exportPhenopacket: vi.fn(),
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('@/composables/useSeoMeta', () => ({
  usePhenopacketSeo: vi.fn(),
  useBreadcrumbStructuredData: vi.fn(),
}));

vi.mock('@/composables/usePhenopacketState', () => ({
  effectiveStateOf: vi.fn(
    (phenopacket) => phenopacket?.effective_state ?? phenopacket?.state ?? null
  ),
  usePhenopacketState: vi.fn(),
}));

vi.mock('vue-router', () => ({
  useRoute: vi.fn(),
}));

import { exportPhenopacket, getPhenopacket } from '@/api';
import { useAuthStore } from '@/stores/authStore';
import { usePhenopacketState } from '@/composables/usePhenopacketState';
import { useRoute } from 'vue-router';

const basePhenopacketResponse = {
  id: 'record-uuid',
  phenopacket: {
    id: 'PP-001',
    subject: {
      id: 'SUB-001',
      sex: 'UNKNOWN_SEX',
    },
    phenotypicFeatures: [],
    interpretations: [],
    measurements: [],
    metaData: {},
  },
  revision: 7,
  effective_state: 'approved',
};

function createAuthStore(role) {
  return reactive({
    user: {
      id: 42,
      username: `${role}.user`,
      role,
    },
    isCurator: ['curator', 'admin'].includes(role),
  });
}

describe('PagePhenopacket', () => {
  let loadHistoryMock;
  let transitionToMock;

  beforeEach(() => {
    vi.resetAllMocks();
    loadHistoryMock = vi.fn().mockResolvedValue(undefined);
    transitionToMock = vi.fn();

    window.logService = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };

    useRoute.mockReturnValue({
      params: {
        phenopacket_id: 'PP-001',
      },
      path: '/phenopackets/PP-001',
    });

    getPhenopacket.mockResolvedValue({ data: basePhenopacketResponse });
    exportPhenopacket.mockResolvedValue({ data: basePhenopacketResponse.phenopacket });

    usePhenopacketState.mockReturnValue({
      revisions: { value: [] },
      historyEntries: { value: [] },
      historyLoading: { value: false },
      historyError: { value: null },
      transitionTo: transitionToMock,
      loadHistory: loadHistoryMock,
      loadRevisions: vi.fn(),
    });
  });

  it('copies only the authoritative server-redacted export representation', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    exportPhenopacket.mockResolvedValue({
      data: { id: 'PP-001', subject: { id: 'SUB-001' } },
    });
    const ctx = {
      phenopacket: { id: 'PP-001', hnf1bCuration: { observationsById: { private: {} } } },
    };

    await PagePhenopacket.methods.copyToClipboard.call(ctx);

    expect(exportPhenopacket).toHaveBeenCalledWith('PP-001');
    expect(writeText).toHaveBeenCalledWith(
      JSON.stringify({ id: 'PP-001', subject: { id: 'SUB-001' } }, null, 2)
    );
    expect(writeText.mock.calls[0][0]).not.toContain('hnf1bCuration');
  });

  it('shows the History tab for curator users', async () => {
    useAuthStore.mockReturnValue(createAuthStore('curator'));

    const wrapper = shallowMount(PagePhenopacket, {
      global: {
        mocks: {
          $route: {
            params: { phenopacket_id: 'PP-001' },
            path: '/phenopackets/PP-001',
          },
          $router: {
            push: vi.fn(),
            back: vi.fn(),
          },
        },
        stubs: {
          HistoryTab: true,
        },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain('Timeline');
    expect(wrapper.text()).toContain('History');
    expect(loadHistoryMock).not.toHaveBeenCalled();
  });

  it('hides the History tab for non-curator users', async () => {
    useAuthStore.mockReturnValue(createAuthStore('viewer'));

    const wrapper = shallowMount(PagePhenopacket, {
      global: {
        mocks: {
          $route: {
            params: { phenopacket_id: 'PP-001' },
            path: '/phenopackets/PP-001',
          },
          $router: {
            push: vi.fn(),
            back: vi.fn(),
          },
        },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain('Timeline');
    expect(wrapper.text()).not.toContain('History');
    expect(loadHistoryMock).not.toHaveBeenCalled();
  });

  it('loads history lazily when a curator opens the History tab', async () => {
    useAuthStore.mockReturnValue(createAuthStore('curator'));

    const wrapper = shallowMount(PagePhenopacket, {
      global: {
        mocks: {
          $route: {
            params: { phenopacket_id: 'PP-001' },
            path: '/phenopackets/PP-001',
          },
          $router: {
            push: vi.fn(),
            back: vi.fn(),
          },
        },
      },
    });

    await flushPromises();
    expect(loadHistoryMock).not.toHaveBeenCalled();

    wrapper.vm.activeTab = 'history';
    await flushPromises();

    expect(loadHistoryMock).toHaveBeenCalledTimes(1);
  });

  it('reloads history after a successful transition when History is active', async () => {
    useAuthStore.mockReturnValue(createAuthStore('curator'));
    transitionToMock.mockResolvedValueOnce({});

    const wrapper = shallowMount(PagePhenopacket, {
      global: {
        mocks: {
          $route: {
            params: { phenopacket_id: 'PP-001' },
            path: '/phenopackets/PP-001',
          },
          $router: {
            push: vi.fn(),
            back: vi.fn(),
          },
        },
      },
    });

    await flushPromises();
    wrapper.vm.activeTab = 'history';
    await flushPromises();
    expect(loadHistoryMock).toHaveBeenCalledTimes(1);

    wrapper.vm.pendingTargetState = 'approved';
    wrapper.vm.phenopacketMeta = { revision: 7 };

    await wrapper.vm.onTransitionConfirm({ reason: 'Approved after review' });

    expect(transitionToMock).toHaveBeenCalledWith('approved', 'Approved after review', 7);
    expect(loadHistoryMock).toHaveBeenCalledTimes(2);
  });

  it('loads history when curator access becomes available while History is active', async () => {
    const authStore = createAuthStore('viewer');
    useAuthStore.mockReturnValue(authStore);

    const wrapper = shallowMount(PagePhenopacket, {
      global: {
        mocks: {
          $route: {
            params: { phenopacket_id: 'PP-001' },
            path: '/phenopackets/PP-001',
          },
          $router: {
            push: vi.fn(),
            back: vi.fn(),
          },
        },
      },
    });

    await flushPromises();
    wrapper.vm.activeTab = 'history';
    await flushPromises();
    expect(loadHistoryMock).not.toHaveBeenCalled();

    authStore.isCurator = true;
    authStore.user.role = 'curator';
    await nextTick();

    expect(loadHistoryMock).toHaveBeenCalledTimes(1);
  });

  it('deduplicates in-flight history loads', async () => {
    useAuthStore.mockReturnValue(createAuthStore('curator'));

    let resolveHistoryLoad;
    loadHistoryMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveHistoryLoad = resolve;
        })
    );

    const wrapper = shallowMount(PagePhenopacket, {
      global: {
        mocks: {
          $route: {
            params: { phenopacket_id: 'PP-001' },
            path: '/phenopackets/PP-001',
          },
          $router: {
            push: vi.fn(),
            back: vi.fn(),
          },
        },
      },
    });

    await flushPromises();

    const firstLoad = wrapper.vm.ensureHistoryLoaded();
    const secondLoad = wrapper.vm.ensureHistoryLoaded();
    await nextTick();

    expect(loadHistoryMock).toHaveBeenCalledTimes(1);

    resolveHistoryLoad();
    await Promise.all([firstLoad, secondLoad]);
    await flushPromises();

    expect(wrapper.vm.historyLoaded).toBe(true);
  });

  it('forces a fresh history reload after a transition even if an older load is in flight', async () => {
    useAuthStore.mockReturnValue(createAuthStore('curator'));
    transitionToMock.mockResolvedValueOnce({});

    let resolveFirstHistoryLoad;
    loadHistoryMock
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirstHistoryLoad = resolve;
          })
      )
      .mockResolvedValueOnce(undefined);

    const wrapper = shallowMount(PagePhenopacket, {
      global: {
        mocks: {
          $route: {
            params: { phenopacket_id: 'PP-001' },
            path: '/phenopackets/PP-001',
          },
          $router: {
            push: vi.fn(),
            back: vi.fn(),
          },
        },
      },
    });

    await flushPromises();
    wrapper.vm.activeTab = 'history';
    await nextTick();

    const inFlightLoad = wrapper.vm.historyLoadPromise;
    expect(loadHistoryMock).toHaveBeenCalledTimes(1);

    wrapper.vm.pendingTargetState = 'approved';
    wrapper.vm.phenopacketMeta = { revision: 7 };

    const transitionPromise = wrapper.vm.onTransitionConfirm({ reason: 'Approved after review' });
    resolveFirstHistoryLoad();

    await Promise.all([inFlightLoad, transitionPromise]);
    await flushPromises();

    expect(transitionToMock).toHaveBeenCalledWith('approved', 'Approved after review', 7);
    expect(loadHistoryMock).toHaveBeenCalledTimes(2);
  });

  /**
   * Curation console Task 9 (design spec §3.5, plan Task 9): a fetus subject
   * saved via AgeSection.vue's writer -- `timeAtLastEncounter:
   * {gestationalAge: {weeks, days}}` -- must show a real age chip instead of
   * silently falling through to `ageDisplay === 'N/A'` (which hides the chip
   * entirely, per the `v-if="ageDisplay !== 'N/A'"` guard in the template).
   */
  it('shows a gestational-age chip for a fetus subject instead of hiding it as N/A', async () => {
    useAuthStore.mockReturnValue(createAuthStore('viewer'));
    getPhenopacket.mockResolvedValue({
      data: {
        ...basePhenopacketResponse,
        phenopacket: {
          ...basePhenopacketResponse.phenopacket,
          subject: {
            id: 'SUB-FETUS-1',
            sex: 'UNKNOWN_SEX',
            timeAtLastEncounter: { gestationalAge: { weeks: 32, days: 3 } },
          },
        },
      },
    });

    const wrapper = shallowMount(PagePhenopacket, {
      global: {
        mocks: {
          $route: {
            params: { phenopacket_id: 'PP-001' },
            path: '/phenopackets/PP-001',
          },
          $router: {
            push: vi.fn(),
            back: vi.fn(),
          },
        },
      },
    });

    await flushPromises();

    expect(wrapper.vm.ageDisplay).toBe('32 weeks 3 days');
    expect(wrapper.text()).toContain('32 weeks 3 days');
  });
});
