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

vi.mock('@/api/domain/phenopackets', () => ({
  transitionPhenopacket: vi.fn(),
  fetchRevisions: vi.fn(),
  getPhenopacketAuditHistory: vi.fn(),
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('@/composables/useSeoMeta', () => ({
  usePhenopacketSeo: vi.fn(),
  useBreadcrumbStructuredData: vi.fn(),
}));

vi.mock('vue-router', () => ({
  useRoute: vi.fn(),
}));

import { getPhenopacket } from '@/api';
import {
  fetchRevisions,
  getPhenopacketAuditHistory,
  transitionPhenopacket,
} from '@/api/domain/phenopackets';
import { getReviewContext } from '@/api/domain/reviews';
import { useAuthStore } from '@/stores/authStore';
import { useRoute } from 'vue-router';

function deferred() {
  let resolve;
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function detail(phenopacketId, revision) {
  return {
    id: `record-${phenopacketId}`,
    phenopacket_id: phenopacketId,
    phenopacket: {
      id: `content-${phenopacketId}`,
      subject: { id: `subject-${phenopacketId}`, sex: 'UNKNOWN_SEX' },
      phenotypicFeatures: [],
      interpretations: [],
      measurements: [],
      metaData: {},
    },
    revision,
    state: 'draft',
    effective_state: 'draft',
    editing_revision_id: null,
    draft_owner_id: 42,
    draft_owner_username: 'curator.user',
    transition_capabilities: [{ action: 'submit', allowed: true, blocked_by: [] }],
  };
}

function context(phenopacketId, revision) {
  return {
    record_id: `record-${phenopacketId}`,
    phenopacket_id: phenopacketId,
    subject_label: `subject-${phenopacketId}`,
    physical_state: 'draft',
    effective_state: 'draft',
    record_revision: revision,
    has_published_head: false,
    owner: { id: 42, username: 'curator.user', display_name: null },
    candidate: null,
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
    capabilities: [{ action: 'submit', allowed: true, blocked_by: [] }],
  };
}

describe('PagePhenopacket route reuse', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    window.logService = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };
    useAuthStore.mockReturnValue(
      reactive({
        user: { id: 42, username: 'curator.user', role: 'curator' },
        isCurator: true,
      })
    );
  });

  it('reloads from a reactive route id and keeps history and transitions on the new record', async () => {
    const staleDetail = deferred();
    const route = reactive({
      params: { phenopacket_id: 'PP-001' },
      path: '/phenopackets/PP-001',
    });
    useRoute.mockReturnValue(route);
    getPhenopacket.mockImplementation((id) =>
      id === 'PP-001' ? staleDetail.promise : Promise.resolve({ data: detail('PP-002', 2) })
    );
    getReviewContext.mockResolvedValue({ data: context('PP-002', 2) });
    fetchRevisions.mockResolvedValue({
      data: {
        data: [
          {
            id: 22,
            revision_number: 2,
            state: 'draft',
            actor_username: 'curator.user',
            created_at: '2026-08-30T12:00:00Z',
            change_reason: 'New record revision',
          },
        ],
        meta: { total: 1 },
      },
    });
    getPhenopacketAuditHistory.mockResolvedValue({ data: [] });
    transitionPhenopacket.mockResolvedValue({
      data: { phenopacket: detail('PP-002', 3), revision: 3 },
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

    expect(getPhenopacket).toHaveBeenCalledWith('PP-002');
    expect(wrapper.vm.phenopacketMeta.phenopacket_id).toBe('PP-002');

    staleDetail.resolve({ data: detail('PP-001', 1) });
    await flushPromises();
    expect(wrapper.vm.phenopacketMeta.phenopacket_id).toBe('PP-002');

    wrapper.vm.activeTab = 'history';
    await nextTick();
    await flushPromises();
    expect(fetchRevisions).toHaveBeenCalledWith('PP-002', undefined);
    expect(getPhenopacketAuditHistory).toHaveBeenCalledWith('PP-002');

    wrapper.vm.pendingTargetState = 'in_review';
    await wrapper.vm.onTransitionConfirm({ reason: 'Submit the new record' });

    expect(transitionPhenopacket).toHaveBeenCalledTimes(1);
    expect(transitionPhenopacket).toHaveBeenCalledWith(
      'PP-002',
      'in_review',
      'Submit the new record',
      2
    );
    expect(transitionPhenopacket).not.toHaveBeenCalledWith(
      'PP-001',
      expect.anything(),
      expect.anything(),
      expect.anything()
    );
  });
});
