import { nextTick, reactive, ref } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';

const contextFixture = () => ({
  record_id: '4c096c55-8f3e-48d3-a759-c57851f3aa31',
  phenopacket_id: 'PP-317',
  subject_label: 'HNF1B renal cysts',
  physical_state: 'published',
  effective_state: 'in_review',
  record_revision: 11,
  has_published_head: true,
  candidate: {
    id: 42,
    revision_number: 7,
    content_sha256: `sha256:${'a'.repeat(64)}`,
    content: {
      id: 'PP-317',
      subject: { id: 'subject-317' },
      hnf1bCuration: { extension: 'visible in raw JSON' },
    },
  },
  baseline: { id: 40, content: { id: 'PP-317', subject: { id: 'old-subject' } } },
  approved: null,
  semantic_changes: [
    {
      section: 'Subject',
      operation: 'changed',
      path: '/subject/id',
      before: 'old-subject',
      after: 'subject-317',
    },
  ],
  audit: {
    owner: { username: 'owner' },
    submission: { id: 42, actor: { username: 'submitter' } },
    contributors: [],
    approval: null,
    publication: { id: 40, actor: { username: 'publisher' } },
  },
  discussion_summary: {
    total_comments: 5,
    ordinary_comments: 3,
    blocking_issues: 2,
    open_blocking_issues: 1,
  },
  issues: [{ id: 55, body_markdown: 'Correct the evidence.' }],
  capabilities: [
    { action: 'create_issue', allowed: true, blocked_by: [] },
    { action: 'request_changes', allowed: true, blocked_by: [] },
    { action: 'approve', allowed: false, blocked_by: ['unresolved_review_issues'] },
  ],
});

const review = {
  context: ref(null),
  loading: ref(false),
  error: ref(null),
  conflict: ref(null),
  liveMessage: ref(''),
  load: vi.fn(),
  reload: vi.fn(),
  markConflict: vi.fn(),
  clearConflict: vi.fn(),
};
const history = {
  historyEntries: ref([
    {
      id: '42',
      revisionNumber: 7,
      state: 'in_review',
      actor: 'submitter',
      timestamp: '2026-08-14T08:30:00Z',
      summary: 'Ready for review',
    },
  ]),
  historyTotal: ref(1),
  historyLoading: ref(false),
  historyError: ref(null),
  loadHistory: vi.fn(),
};
const route = reactive({
  params: { phenopacket_id: 'PP-317' },
  query: { return_to: '/review?tab=approved&page=2&q=renal' },
});

vi.mock('@/composables/useReviewContext', () => ({ useReviewContext: () => review }));
vi.mock('@/composables/usePhenopacketState', () => ({ usePhenopacketState: () => history }));
vi.mock('vue-router', () => ({ useRoute: () => route }));

import PhenopacketReview from '@/views/PhenopacketReview.vue';
import reviewWorkspaceSource from '@/views/PhenopacketReview.vue?raw';

const ReviewHeaderStub = {
  props: ['context', 'returnTo'],
  template:
    '<header data-testid="review-header" :data-return-to="returnTo"><h1>Review {{ context.phenopacket_id }}</h1></header>',
};
const ReviewIssuesPanelStub = {
  props: [
    'issues',
    'recordId',
    'recordRevision',
    'candidateRevisionId',
    'createIssueCapability',
    'reload',
    'liveMessage',
  ],
  template: '<section data-testid="issues-panel">Issues {{ issues.length }}</section>',
};
const ReviewActionPanelStub = {
  props: ['context', 'reload', 'onCompleted'],
  template: '<section data-testid="action-panel">Decisions</section>',
};
const tabsStub = {
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<div><slot /></div>',
};
const tabStub = {
  props: ['value'],
  emits: ['click'],
  template:
    '<button class="content-tab" @click="$parent.$emit(`update:modelValue`, value)"><slot /></button>',
};

const stubs = {
  ReviewHeader: ReviewHeaderStub,
  SemanticDiff: { template: '<section data-testid="semantic-diff">Semantic changes</section>' },
  CandidateSnapshot: {
    template: '<section data-testid="candidate-snapshot">Candidate snapshot</section>',
  },
  ReviewIssuesPanel: ReviewIssuesPanelStub,
  ReviewActionPanel: ReviewActionPanelStub,
  HistoryTab: {
    props: ['entries', 'total', 'loading', 'error'],
    template:
      '<section data-testid="history-view">History {{ entries.length }} of {{ total }}</section>',
  },
  'v-container': { template: '<main><slot /></main>' },
  'v-tabs': tabsStub,
  'v-tab': tabStub,
  'v-alert': { template: '<section role="alert"><slot /><slot name="append" /></section>' },
  'v-btn': {
    name: 'VBtn',
    props: ['to'],
    template: '<button :data-route-name="to && to.name"><slot name="prepend" /><slot /></button>',
  },
  'v-icon': { template: '<i aria-hidden="true"><slot /></i>' },
  'v-skeleton-loader': { template: '<div data-testid="workspace-skeleton" />' },
};

const mountedWrappers = new Set();

function mountWorkspace({ attachTo } = {}) {
  const wrapper = mount(PhenopacketReview, { attachTo, global: { stubs } });
  mountedWrappers.add(wrapper);
  return wrapper;
}

function precedes(left, right) {
  return Boolean(left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_FOLLOWING);
}

describe('PhenopacketReview', () => {
  afterEach(() => {
    for (const wrapper of mountedWrappers) wrapper.unmount();
    mountedWrappers.clear();
    document.body.innerHTML = '';
  });

  beforeEach(() => {
    vi.clearAllMocks();
    route.params.phenopacket_id = 'PP-317';
    review.context.value = contextFixture();
    review.loading.value = false;
    review.error.value = null;
    review.liveMessage.value = '';
    review.load.mockResolvedValue(review.context.value);
    review.reload.mockResolvedValue(review.context.value);
    history.loadHistory.mockResolvedValue(undefined);
    history.historyEntries.value = [
      { id: '42', revisionNumber: 7, state: 'in_review', actor: 'submitter' },
    ];
    history.historyTotal.value = 1;
    history.historyLoading.value = false;
    history.historyError.value = null;
    route.query.return_to = '/review?tab=approved&page=2&q=renal';
  });

  it('renders a stable skeleton with one h1 while the coherent context is loading', () => {
    review.context.value = null;
    review.loading.value = true;
    const wrapper = mountWorkspace();

    expect(wrapper.findAll('h1')).toHaveLength(1);
    expect(wrapper.get('[data-testid="workspace-skeleton"]').exists()).toBe(true);
    expect(wrapper.get('[aria-busy="true"]').exists()).toBe(true);
  });

  it('renders a private-safe 404 without disclosing record existence', () => {
    review.context.value = null;
    review.error.value = Object.assign(new Error('secret record exists'), {
      response: { status: 404 },
    });
    const wrapper = mountWorkspace();

    expect(wrapper.text()).toContain('Review workspace not found');
    expect(wrapper.text()).toContain('unavailable or you do not have access');
    expect(wrapper.text()).not.toContain('secret record exists');
    expect(wrapper.text()).not.toContain('Retry');
  });

  it('keeps a retry action for non-404 loading failures', async () => {
    review.context.value = null;
    review.error.value = new Error('Network unavailable');
    const wrapper = mountWorkspace();

    expect(wrapper.get('[role="alert"]').text()).toContain('Network unavailable');
    await wrapper.get('[data-testid="retry-review-context"]').trigger('click');
    expect(review.load).toHaveBeenCalled();
  });

  it('preserves the exact return-to query for the header and renders one h1', () => {
    const wrapper = mountWorkspace();

    expect(wrapper.findAll('h1')).toHaveLength(1);
    expect(wrapper.get('[data-testid="review-header"]').attributes('data-return-to')).toBe(
      '/review?tab=approved&page=2&q=renal'
    );
  });

  it('renders changes, candidate, complete raw JSON, and refreshed history views', async () => {
    const wrapper = mountWorkspace();
    await flushPromises();
    expect(wrapper.get('[data-testid="semantic-diff"]').exists()).toBe(true);
    expect(history.loadHistory).toHaveBeenCalled();

    const tabs = wrapper.findAll('.content-tab');
    await tabs.find((tab) => tab.text() === 'Candidate').trigger('click');
    expect(wrapper.get('[data-testid="candidate-snapshot"]').exists()).toBe(true);

    await tabs.find((tab) => tab.text() === 'Raw JSON').trigger('click');
    expect(wrapper.get('[data-testid="raw-json"]').text()).toContain('hnf1bCuration');
    expect(wrapper.get('[data-testid="raw-json"]').text()).toContain('visible in raw JSON');

    await tabs.find((tab) => tab.text() === 'History').trigger('click');
    expect(wrapper.get('[data-testid="history-view"]').text()).toContain('History 1');
  });

  it('uses context reload as the mutation boundary then refreshes history and announces completion', async () => {
    const wrapper = mountWorkspace();
    await flushPromises();
    history.loadHistory.mockClear();
    const panel = wrapper.getComponent(ReviewActionPanelStub);

    await panel.props('onCompleted')({ action: 'approve' });
    await nextTick();

    expect(history.loadHistory).toHaveBeenCalledOnce();
    expect(wrapper.get('[role="status"]').attributes('aria-live')).toBe('polite');
    expect(wrapper.get('[role="status"]').text()).toContain('Review decision saved');
  });

  it('replaces a vanished published context with a stable focused completion state', async () => {
    const wrapper = mountWorkspace({ attachTo: document.body });
    await flushPromises();
    const onCompleted = wrapper.getComponent(ReviewActionPanelStub).props('onCompleted');
    review.context.value = null;
    review.error.value = Object.assign(new Error('Expected terminal context 404'), {
      response: { status: 404 },
    });

    await onCompleted({ action: 'publish', context: null });
    await nextTick();

    expect(wrapper.findComponent(ReviewActionPanelStub).exists()).toBe(false);
    expect(wrapper.text()).toContain('Publication complete');
    expect(wrapper.text()).toContain('The approved revision is now public');
    expect(wrapper.text()).not.toContain('Review workspace not found');
    const heading = wrapper.get('[data-testid="publication-complete-heading"]');
    expect(document.activeElement).toBe(heading.element);
    expect(wrapper.get('[data-testid="publication-complete-queue"]').attributes()).toMatchObject({
      'data-route-name': 'ReviewQueue',
    });

    review.error.value = new Error('Stale reload rejection');
    await nextTick();
    expect(wrapper.get('[data-testid="publication-complete-heading"]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('Unable to load review workspace');
  });

  it('assembles a desktop right rail with exact issues, decisions, discussion source order', () => {
    const wrapper = mountWorkspace();
    const content = wrapper.get('[data-testid="content-column"]').element;
    const rail = wrapper.get('[data-testid="review-right-rail"]');
    const issues = wrapper.get('[data-testid="issues-panel"]').element;
    const decisions = wrapper.get('[data-testid="action-panel"]').element;
    const issueSection = wrapper.get('[data-testid="issues-rail-section"]').element;
    const decisionSection = wrapper.get('[data-testid="decision-rail-section"]').element;
    const discussionSection = wrapper.get('[data-testid="discussion-rail-section"]').element;

    expect(rail.classes()).toContain('review-right-rail');
    expect(wrapper.get('[data-testid="decision-rail-section"]').classes()).toContain(
      'mobile-safe-decision'
    );
    expect(precedes(content, issues)).toBe(true);
    expect(precedes(issues, decisions)).toBe(true);
    expect(issueSection.nextElementSibling).toBe(decisionSection);
    expect(decisionSection.nextElementSibling).toBe(discussionSection);
  });

  it('keeps the mobile decision rail sticky above the safe area without CSS reordering', () => {
    expect(reviewWorkspaceSource).toMatch(/@media \(max-width: 959px\)/);
    expect(reviewWorkspaceSource).toContain(
      'padding-bottom: calc(1rem + env(safe-area-inset-bottom));'
    );
    expect(reviewWorkspaceSource).not.toMatch(/\border\s*:/);
  });

  it('passes exact context identities and server capabilities to issues and decisions', () => {
    const wrapper = mountWorkspace();
    const issues = wrapper.getComponent(ReviewIssuesPanelStub);
    const actions = wrapper.getComponent(ReviewActionPanelStub);

    expect(issues.props()).toMatchObject({
      recordId: '4c096c55-8f3e-48d3-a759-c57851f3aa31',
      recordRevision: 11,
      candidateRevisionId: 42,
      createIssueCapability: { action: 'create_issue', allowed: true, blocked_by: [] },
    });
    expect(actions.props('context')).toBe(review.context.value);
  });
});
