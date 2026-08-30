import { nextTick } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createMemoryHistory, createRouter } from 'vue-router';

const { getReviewContext, fetchRevisions, getPhenopacketAuditHistory } = vi.hoisted(() => ({
  getReviewContext: vi.fn(),
  fetchRevisions: vi.fn(),
  getPhenopacketAuditHistory: vi.fn(),
}));

vi.mock('@/api/domain/reviews', () => ({ getReviewContext }));
vi.mock('@/api/domain/phenopackets', () => ({
  fetchRevisions,
  getPhenopacketAuditHistory,
  transitionPhenopacket: vi.fn(),
}));

import PhenopacketReview from '@/views/PhenopacketReview.vue';

function contextFixture(id) {
  return {
    record_id: `00000000-0000-4000-8000-0000000000${id === 'PP-A' ? '01' : '02'}`,
    phenopacket_id: id,
    subject_label: `Subject ${id}`,
    physical_state: 'published',
    effective_state: 'in_review',
    record_revision: id === 'PP-A' ? 1 : 2,
    has_published_head: true,
    candidate: {
      id: id === 'PP-A' ? 10 : 20,
      revision_number: id === 'PP-A' ? 1 : 2,
      content_sha256: `sha256:${id === 'PP-A' ? 'a' : 'b'}`.padEnd(71, id === 'PP-A' ? 'a' : 'b'),
      content: { id, subject: { id: `subject-${id}` } },
    },
    baseline: null,
    approved: null,
    semantic_changes: [{ section: 'Subject', operation: 'added', path: '/subject' }],
    audit: { owner: null, submission: null, contributors: [], approval: null, publication: null },
    discussion_summary: {
      total_comments: 0,
      ordinary_comments: 0,
      blocking_issues: 0,
      open_blocking_issues: 0,
    },
    issues: [],
    capabilities: [{ action: 'request_changes', allowed: true, blocked_by: [] }],
  };
}

function revisionResponse(id) {
  return {
    data: {
      data: [
        {
          id: id === 'PP-A' ? 10 : 20,
          revision_number: id === 'PP-A' ? 1 : 2,
          state: 'in_review',
          actor_username: `curator-${id}`,
          created_at: '2026-08-30T10:00:00Z',
        },
      ],
      meta: { total: 1, page: 1, page_size: 50 },
    },
  };
}

function deferred() {
  let resolve;
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

const ReviewHeaderStub = {
  props: ['context'],
  template:
    '<header><h1 data-testid="route-record">Review {{ context.phenopacket_id }}</h1></header>',
};
const ReviewActionPanelStub = {
  props: ['context', 'reload', 'onCompleted'],
  data: () => ({ localConflict: false }),
  template:
    '<section data-testid="route-actions">Actions {{ context.phenopacket_id }} <button data-testid="set-local-conflict" @click="localConflict = true">Conflict</button><span data-testid="local-conflict">{{ localConflict }}</span></section>',
};
const tabsStub = {
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<div><slot /></div>',
};
const tabStub = {
  props: ['value'],
  template:
    '<button class="route-content-tab" @click="$parent.$emit(`update:modelValue`, value)"><slot /></button>',
};
const stubs = {
  ReviewHeader: ReviewHeaderStub,
  ReviewActionPanel: ReviewActionPanelStub,
  ReviewIssuesPanel: { template: '<section data-testid="route-issues">Issues</section>' },
  SemanticDiff: { template: '<section data-testid="route-changes">Changes</section>' },
  CandidateSnapshot: {
    props: ['candidate'],
    template:
      '<section data-testid="route-candidate">Candidate {{ candidate.content.id }}</section>',
  },
  HistoryTab: { template: '<section data-testid="route-history">History</section>' },
  'v-container': { template: '<main><slot /></main>' },
  'v-tabs': tabsStub,
  'v-tab': tabStub,
  'v-alert': { template: '<section role="alert"><slot /><slot name="append" /></section>' },
  'v-btn': { template: '<button><slot /></button>' },
  'v-skeleton-loader': { template: '<div data-testid="workspace-skeleton" />' },
};

async function mountAt(path) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/review/:phenopacket_id', component: PhenopacketReview }],
  });
  await router.push(path);
  await router.isReady();
  const wrapper = mount({ template: '<router-view />' }, { global: { plugins: [router], stubs } });
  await flushPromises();
  return { router, wrapper };
}

describe('PhenopacketReview route reuse', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getPhenopacketAuditHistory.mockResolvedValue({ data: [] });
    fetchRevisions.mockImplementation((id) => Promise.resolve(revisionResponse(id)));
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('ignores a deferred A context after the reused router view loads B', async () => {
    const staleA = deferred();
    getReviewContext.mockImplementation((id) => {
      if (id === 'PP-A') return staleA.promise;
      return Promise.resolve({ data: contextFixture(id) });
    });
    const { router, wrapper } = await mountAt('/review/PP-A');

    await router.push('/review/PP-B');
    await flushPromises();
    expect(wrapper.get('[data-testid="route-record"]').text()).toContain('PP-B');
    expect(wrapper.get('[data-testid="route-actions"]').text()).toContain('PP-B');
    expect(fetchRevisions).toHaveBeenCalledWith('PP-B', undefined);

    staleA.resolve({ data: contextFixture('PP-A') });
    await flushPromises();
    expect(wrapper.get('[data-testid="route-record"]').text()).toContain('PP-B');
    expect(wrapper.text()).not.toContain('Subject PP-A');
  });

  it('resets completion, tab, and keyed action state and rejects late A completion on B', async () => {
    const staleAHistory = deferred();
    let aHistoryCalls = 0;
    getReviewContext.mockImplementation((id) => Promise.resolve({ data: contextFixture(id) }));
    fetchRevisions.mockImplementation((id) => {
      if (id === 'PP-A' && ++aHistoryCalls === 1) return staleAHistory.promise;
      return Promise.resolve(revisionResponse(id));
    });
    const { router, wrapper } = await mountAt('/review/PP-A');
    const tabs = wrapper.findAll('.route-content-tab');
    await tabs.find((tab) => tab.text() === 'Candidate').trigger('click');
    expect(wrapper.get('[data-testid="route-candidate"]').text()).toContain('PP-A');
    await wrapper.get('[data-testid="set-local-conflict"]').trigger('click');
    expect(wrapper.get('[data-testid="local-conflict"]').text()).toBe('true');
    const oldCompletion = wrapper.getComponent(ReviewActionPanelStub).props('onCompleted');
    await oldCompletion({ action: 'publish', recordId: 'PP-A' });
    expect(wrapper.text()).toContain('Publication complete');

    await router.push('/review/PP-B');
    await flushPromises();
    expect(wrapper.get('[data-testid="route-record"]').text()).toContain('PP-B');
    expect(wrapper.get('[data-testid="route-changes"]').exists()).toBe(true);
    expect(wrapper.get('[data-testid="local-conflict"]').text()).toBe('false');

    await oldCompletion({ action: 'publish', recordId: 'PP-A' });
    await nextTick();
    staleAHistory.resolve(revisionResponse('PP-A'));
    await flushPromises();
    expect(wrapper.get('[data-testid="route-record"]').text()).toContain('PP-B');
    expect(wrapper.text()).not.toContain('Publication complete');
  });
});
