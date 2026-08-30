import { flushPromises, shallowMount } from '@vue/test-utils';
import { nextTick, reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PagePhenopacket from '@/views/PagePhenopacket.vue';

vi.mock('@/api', () => ({
  getPhenopacket: vi.fn(),
  deletePhenopacket: vi.fn(),
  exportPhenopacket: vi.fn(),
}));

vi.mock('@/api/domain/reviews', () => ({
  getReviewContext: vi.fn(),
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
import { getReviewContext } from '@/api/domain/reviews';
import { useAuthStore } from '@/stores/authStore';
import { usePhenopacketState } from '@/composables/usePhenopacketState';
import { useRoute } from 'vue-router';

const basePhenopacketResponse = {
  id: 'record-uuid',
  phenopacket_id: 'PP-001',
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
  transition_capabilities: [{ action: 'archive', allowed: false, blocked_by: ['forbidden_role'] }],
};

const reviewContextResponse = {
  record_id: 'record-uuid',
  phenopacket_id: 'PP-001',
  subject_label: 'SUB-001',
  physical_state: 'approved',
  effective_state: 'approved',
  record_revision: 7,
  has_published_head: false,
  owner: { id: 42, username: 'curator.user', display_name: null },
  candidate: {
    id: 12,
    revision_number: 7,
    state: 'in_review',
    content_sha256: `sha256:${'1'.repeat(64)}`,
    created_at: '2026-08-30T10:00:00Z',
    actor: { id: 42, username: 'curator.user', display_name: null },
    actor_role: 'curator',
    actor_role_at_decision_recorded: true,
    content: { id: 'PP-001' },
  },
  baseline: null,
  approved: null,
  semantic_changes: [],
  audit: {
    owner: { id: 42, username: 'curator.user', display_name: null },
    submission: null,
    contributors: [],
    approval: null,
    publication: null,
  },
  discussion_summary: {
    total_comments: 0,
    ordinary_comments: 0,
    blocking_issues: 0,
    open_blocking_issues: 0,
  },
  issues: [],
  capabilities: [
    { action: 'request_changes', allowed: true, blocked_by: [] },
    { action: 'publish', allowed: false, blocked_by: ['forbidden_role'] },
    { action: 'archive', allowed: false, blocked_by: ['forbidden_role'] },
  ],
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

function deferred() {
  let resolve;
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
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
    getReviewContext.mockResolvedValue({ data: reviewContextResponse });
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

    wrapper.vm.pendingTargetState = 'archived';
    wrapper.vm.phenopacketMeta = { ...basePhenopacketResponse, revision: 7 };

    await wrapper.vm.onTransitionConfirm({ reason: 'Archive obsolete record' });

    expect(transitionToMock).toHaveBeenCalledWith('archived', 'Archive obsolete record', 7);
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

    wrapper.vm.pendingTargetState = 'archived';
    wrapper.vm.phenopacketMeta = { ...basePhenopacketResponse, revision: 7 };

    const transitionPromise = wrapper.vm.onTransitionConfirm({ reason: 'Archive obsolete record' });
    resolveFirstHistoryLoad();

    await Promise.all([inFlightLoad, transitionPromise]);
    await flushPromises();

    expect(transitionToMock).toHaveBeenCalledWith('archived', 'Archive obsolete record', 7);
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

  it('uses coherent review-context capability ordering and opens the named review route', async () => {
    useAuthStore.mockReturnValue(createAuthStore('curator'));
    getPhenopacket.mockResolvedValue({
      data: {
        ...basePhenopacketResponse,
        phenopacket: {
          ...basePhenopacketResponse.phenopacket,
          id: 'CONTENT-ID-MUST-NOT-BECOME-ROUTE-ID',
        },
      },
    });
    const push = vi.fn();
    const wrapper = shallowMount(PagePhenopacket, {
      global: {
        mocks: {
          $route: {
            params: { phenopacket_id: 'PP-001' },
            path: '/phenopackets/PP-001',
          },
          $router: { push, back: vi.fn() },
        },
      },
    });

    await flushPromises();

    expect(getReviewContext).toHaveBeenCalledTimes(1);
    expect(getReviewContext).toHaveBeenCalledWith('PP-001');
    const menu = wrapper.getComponent({ name: 'TransitionMenu' });
    expect(menu.props('capabilities')).toEqual([
      { action: 'request_changes', allowed: true, blocked_by: [] },
      { action: 'publish', allowed: false, blocked_by: ['forbidden_role'] },
      { action: 'archive', allowed: false, blocked_by: ['forbidden_role'] },
    ]);
    expect(menu.props()).not.toHaveProperty('role');
    expect(menu.props()).not.toHaveProperty('isOwner');
    expect(menu.props()).not.toHaveProperty('currentState');
    expect(wrapper.text()).toContain('Open review workspace');

    menu.vm.$emit('open-review', 'request_changes');
    await nextTick();

    expect(push).toHaveBeenCalledWith({
      name: 'PhenopacketReview',
      params: { phenopacket_id: 'PP-001' },
    });
  });

  it('never unions mismatched revisions and adopts coherent retry context ordering', async () => {
    useAuthStore.mockReturnValue(createAuthStore('curator'));
    const retryDetail = deferred();
    const retryContext = deferred();
    const structuralFallback = [
      { action: 'submit', allowed: true, blocked_by: [] },
      { action: 'archive', allowed: false, blocked_by: ['forbidden_role'] },
    ];
    getPhenopacket
      .mockResolvedValueOnce({
        data: {
          ...basePhenopacketResponse,
          revision: 7,
          effective_state: 'draft',
          transition_capabilities: structuralFallback,
        },
      })
      .mockReturnValueOnce(retryDetail.promise);
    getReviewContext
      .mockResolvedValueOnce({
        data: {
          ...reviewContextResponse,
          effective_state: 'in_review',
          record_revision: 8,
          capabilities: [{ action: 'approve', allowed: true, blocked_by: [] }],
        },
      })
      .mockReturnValueOnce(retryContext.promise);

    const wrapper = shallowMount(PagePhenopacket, {
      global: {
        mocks: {
          $route: {
            params: { phenopacket_id: 'PP-001' },
            path: '/phenopackets/PP-001',
          },
          $router: { push: vi.fn(), back: vi.fn() },
        },
      },
    });
    await flushPromises();

    expect(getPhenopacket).toHaveBeenCalledTimes(2);
    expect(wrapper.vm.reviewContext).toBeNull();
    expect(wrapper.vm.transitionCapabilities).toEqual(structuralFallback);
    expect(wrapper.vm.transitionCapabilities).not.toContainEqual(
      expect.objectContaining({ action: 'approve' })
    );

    retryDetail.resolve({
      data: {
        ...basePhenopacketResponse,
        revision: 8,
        effective_state: 'in_review',
        transition_capabilities: [
          { action: 'archive', allowed: false, blocked_by: ['forbidden_role'] },
        ],
      },
    });
    await flushPromises();
    retryContext.resolve({
      data: {
        ...reviewContextResponse,
        effective_state: 'in_review',
        record_revision: 8,
        capabilities: [
          { action: 'withdraw', allowed: true, blocked_by: [] },
          { action: 'request_changes', allowed: true, blocked_by: [] },
          { action: 'archive', allowed: false, blocked_by: ['forbidden_role'] },
        ],
      },
    });
    await flushPromises();

    expect(getReviewContext).toHaveBeenCalledTimes(2);
    expect(wrapper.vm.transitionCapabilities).toEqual([
      { action: 'withdraw', allowed: true, blocked_by: [] },
      { action: 'request_changes', allowed: true, blocked_by: [] },
      { action: 'archive', allowed: false, blocked_by: ['forbidden_role'] },
    ]);
  });

  it('bounds persistent context mismatch and retains only retry detail structural actions', async () => {
    useAuthStore.mockReturnValue(createAuthStore('curator'));
    getPhenopacket
      .mockResolvedValueOnce({
        data: {
          ...basePhenopacketResponse,
          revision: 7,
          effective_state: 'draft',
          transition_capabilities: [{ action: 'submit', allowed: true, blocked_by: [] }],
        },
      })
      .mockResolvedValueOnce({
        data: {
          ...basePhenopacketResponse,
          revision: 8,
          effective_state: 'in_review',
          transition_capabilities: [
            { action: 'archive', allowed: false, blocked_by: ['forbidden_role'] },
          ],
        },
      });
    getReviewContext
      .mockResolvedValueOnce({
        data: {
          ...reviewContextResponse,
          record_revision: 8,
          capabilities: [{ action: 'approve', allowed: true, blocked_by: [] }],
        },
      })
      .mockResolvedValueOnce({
        data: {
          ...reviewContextResponse,
          record_id: 'different-record-uuid',
          record_revision: 8,
          capabilities: [{ action: 'request_changes', allowed: true, blocked_by: [] }],
        },
      });

    const wrapper = shallowMount(PagePhenopacket, {
      global: {
        mocks: {
          $route: {
            params: { phenopacket_id: 'PP-001' },
            path: '/phenopackets/PP-001',
          },
          $router: { push: vi.fn(), back: vi.fn() },
        },
      },
    });
    await flushPromises();

    expect(getPhenopacket).toHaveBeenCalledTimes(2);
    expect(getReviewContext).toHaveBeenCalledTimes(2);
    expect(wrapper.vm.reviewContext).toBeNull();
    expect(wrapper.vm.transitionCapabilities).toEqual([
      { action: 'archive', allowed: false, blocked_by: ['forbidden_role'] },
    ]);
    expect(wrapper.vm.hasReviewWorkspace).toBe(false);
  });

  it('fails exact review actions closed while retaining detail structural capabilities', async () => {
    useAuthStore.mockReturnValue(createAuthStore('admin'));
    getPhenopacket.mockResolvedValue({
      data: {
        ...basePhenopacketResponse,
        effective_state: 'published',
        transition_capabilities: [{ action: 'archive', allowed: true, blocked_by: [] }],
      },
    });
    getReviewContext.mockRejectedValueOnce(
      Object.assign(new Error('Phenopacket not found'), { response: { status: 404 } })
    );

    const wrapper = shallowMount(PagePhenopacket, {
      global: {
        mocks: {
          $route: {
            params: { phenopacket_id: 'PP-001' },
            path: '/phenopackets/PP-001',
          },
          $router: { push: vi.fn(), back: vi.fn() },
        },
      },
    });

    await flushPromises();

    expect(wrapper.vm.reviewContext).toBeNull();
    expect(wrapper.getComponent({ name: 'TransitionMenu' }).props('capabilities')).toEqual([
      { action: 'archive', allowed: true, blocked_by: [] },
    ]);
    expect(wrapper.text()).not.toContain('Open review workspace');
    expect(window.logService.error).not.toHaveBeenCalled();
  });

  it('ignores a stale context response after a newer detail load owns the request', async () => {
    useAuthStore.mockReturnValue(createAuthStore('curator'));
    const staleContext = deferred();
    const nextDetail = deferred();
    const route = reactive({
      params: { phenopacket_id: 'PP-001' },
      path: '/phenopackets/PP-001',
    });
    useRoute.mockReturnValue(route);
    getPhenopacket.mockImplementation((phenopacketId) => {
      const response = {
        data: {
          ...basePhenopacketResponse,
          phenopacket_id: phenopacketId,
          phenopacket: {
            ...basePhenopacketResponse.phenopacket,
            id: `content-${phenopacketId}`,
          },
        },
      };
      return phenopacketId === 'PP-002' ? nextDetail.promise : Promise.resolve(response);
    });
    getReviewContext.mockImplementation((phenopacketId) => {
      if (phenopacketId === 'PP-001') return staleContext.promise;
      return Promise.resolve({
        data: {
          ...reviewContextResponse,
          phenopacket_id: phenopacketId,
          capabilities: [{ action: 'approve', allowed: true, blocked_by: [] }],
        },
      });
    });

    const wrapper = shallowMount(PagePhenopacket, {
      global: {
        mocks: {
          $route: route,
          $router: { push: vi.fn(), back: vi.fn() },
        },
      },
    });
    await nextTick();
    await nextTick();
    expect(getReviewContext).toHaveBeenCalledWith('PP-001');

    route.params.phenopacket_id = 'PP-002';
    route.path = '/phenopackets/PP-002';
    await nextTick();
    expect(getPhenopacket).toHaveBeenLastCalledWith('PP-002');

    staleContext.resolve({ data: reviewContextResponse });
    await flushPromises();
    expect(wrapper.vm.reviewContext).toBeNull();
    expect(wrapper.vm.loading).toBe(true);

    nextDetail.resolve({
      data: {
        ...basePhenopacketResponse,
        phenopacket_id: 'PP-002',
        phenopacket: { ...basePhenopacketResponse.phenopacket, id: 'content-PP-002' },
      },
    });
    await flushPromises();

    expect(wrapper.vm.reviewContext.phenopacket_id).toBe('PP-002');
    expect(wrapper.vm.transitionCapabilities).toContainEqual({
      action: 'approve',
      allowed: true,
      blocked_by: [],
    });
  });

  it('ignores an older detail response that resolves after the newer record', async () => {
    useAuthStore.mockReturnValue(createAuthStore('curator'));
    const staleDetail = deferred();
    const route = reactive({
      params: { phenopacket_id: 'PP-001' },
      path: '/phenopackets/PP-001',
    });
    useRoute.mockReturnValue(route);
    getPhenopacket.mockImplementation((phenopacketId) => {
      if (phenopacketId === 'PP-001') return staleDetail.promise;
      return Promise.resolve({
        data: {
          ...basePhenopacketResponse,
          phenopacket_id: 'PP-002',
          phenopacket: { ...basePhenopacketResponse.phenopacket, id: 'content-PP-002' },
          transition_capabilities: [{ action: 'archive', allowed: true, blocked_by: [] }],
        },
      });
    });
    getReviewContext.mockResolvedValue({
      data: {
        ...reviewContextResponse,
        phenopacket_id: 'PP-002',
        capabilities: [{ action: 'approve', allowed: true, blocked_by: [] }],
      },
    });

    const wrapper = shallowMount(PagePhenopacket, {
      global: {
        mocks: {
          $route: route,
          $router: { push: vi.fn(), back: vi.fn() },
        },
      },
    });
    await nextTick();
    expect(getPhenopacket).toHaveBeenCalledWith('PP-001');

    route.params.phenopacket_id = 'PP-002';
    route.path = '/phenopackets/PP-002';
    await flushPromises();
    expect(wrapper.vm.phenopacketMeta.phenopacket_id).toBe('PP-002');

    staleDetail.resolve({ data: basePhenopacketResponse });
    await flushPromises();

    expect(wrapper.vm.phenopacketMeta.phenopacket_id).toBe('PP-002');
    expect(wrapper.vm.reviewContext.phenopacket_id).toBe('PP-002');
    expect(wrapper.vm.loading).toBe(false);
  });
});
