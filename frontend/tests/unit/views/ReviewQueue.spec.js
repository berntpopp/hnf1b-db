import { computed, nextTick, reactive, ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';

const queue = {
  items: ref([]),
  meta: ref({ total: 0, total_pages: 0, state_counts: {} }),
  loading: ref(false),
  error: ref(null),
  page: ref(1),
  pageSize: ref(25),
  sort: ref(null),
  search: ref(''),
  tab: ref('needs-review'),
  eligibility: ref('all'),
  issues: ref('all'),
  hasFilters: computed(() => false),
  load: vi.fn(),
  retry: vi.fn(),
  clearFilters: vi.fn(),
  setTab: vi.fn(),
};
const mockRoute = reactive({ fullPath: '/review?tab=approved&page=2' });

vi.mock('@/composables/useReviewQueue', () => ({ useReviewQueue: () => queue }));
vi.mock('vue-router', () => ({ useRoute: () => mockRoute }));

import ReviewQueue from '@/views/ReviewQueue.vue';

const AppDataTableStub = {
  props: ['headers', 'items', 'itemsLength', 'loading'],
  template: `
    <div data-testid="review-table" :data-total="itemsLength" :data-loading="loading">
      <slot name="toolbar" />
      <div v-for="item in items" :key="item.phenopacket_id" class="queue-row">
        <slot name="item.effective_state" :item="item" />
        <slot name="item.open_issue_count" :item="item" />
        <slot name="item.actions" :item="item" />
      </div>
      <slot v-if="!items.length" name="no-data" />
      <slot name="bottom" />
    </div>
  `,
};

const AppTableToolbarStub = {
  name: 'AppTableToolbar',
  props: ['searchQuery'],
  emits: ['update:searchQuery', 'search', 'clear-search'],
  template: `
    <div>
      <button data-testid="search-input-event" @click="$emit('update:searchQuery', 'renal')">
        Input
      </button>
      <button data-testid="debounced-search-event" @click="$emit('search', 'renal')">
        Search
      </button>
      <slot name="actions" />
    </div>
  `,
};

const stubs = {
  AppDataTable: AppDataTableStub,
  AppTableToolbar: AppTableToolbarStub,
  AppPagination: { template: '<div class="pagination-stub" />' },
  StateBadge: { props: ['state'], template: '<span class="state-badge">{{ state }}</span>' },
  'v-container': { template: '<main><slot /></main>' },
  'v-tabs': { template: '<div><slot /></div>' },
  'v-tab': { template: '<button><slot /></button>' },
  'v-select': { template: '<select />' },
  'v-alert': { template: '<section role="alert"><slot /><slot name="append" /></section>' },
  'v-chip': { template: '<span><slot /></span>' },
  'v-btn': {
    name: 'VBtn',
    props: ['to'],
    template:
      '<a v-if="to" class="review-link" :href="`/review/${to.params.phenopacket_id}`"><slot /></a><button v-else><slot /></button>',
  },
  'v-icon': { template: '<i><slot /></i>' },
};

function mountQueue() {
  return mount(ReviewQueue, {
    global: {
      stubs,
    },
  });
}

describe('ReviewQueue', () => {
  beforeEach(() => {
    queue.items.value = [];
    queue.meta.value = { total: 0, total_pages: 0, state_counts: {} };
    queue.loading.value = false;
    queue.error.value = null;
    queue.search.value = '';
    queue.tab.value = 'needs-review';
    queue.hasFilters = computed(() => false);
    mockRoute.fullPath = '/review?tab=approved&page=2';
    queue.retry.mockClear();
    queue.clearFilters.mockClear();
    queue.setTab.mockClear();
  });

  it('uses backend totals and renders effective state with an explicit Review link', () => {
    queue.items.value = [
      {
        phenopacket_id: 'PP-317',
        subject_label: 'Renal cysts',
        physical_state: 'published',
        effective_state: 'in_review',
        open_issue_count: 2,
      },
    ];
    queue.meta.value = { total: 41, total_pages: 2, state_counts: {} };

    const wrapper = mountQueue();

    expect(wrapper.get('[data-testid="review-table"]').attributes('data-total')).toBe('41');
    expect(wrapper.text()).toContain('in_review');
    expect(wrapper.find('a.review-link').attributes('href')).toBe('/review/PP-317');
    expect(wrapper.text()).toContain('2 open issues');
  });

  it('keeps the current reactive queue URL on each explicit Review link', async () => {
    queue.items.value = [
      { phenopacket_id: 'PP-317', effective_state: 'approved', open_issue_count: 0 },
    ];

    const wrapper = mountQueue();
    const reviewLink = wrapper.getComponent({ name: 'VBtn' });

    expect(wrapper.find('a.review-link').exists()).toBe(true);
    expect(reviewLink.props('to').query.return_to).toBe('/review?tab=approved&page=2');

    mockRoute.fullPath = '/review?tab=approved&page=3&q=HNF1B';
    await nextTick();

    expect(reviewLink.props('to').query.return_to).toBe('/review?tab=approved&page=3&q=HNF1B');
  });

  it('does not expose bulk approval or row-click-only navigation', () => {
    queue.items.value = [
      { phenopacket_id: 'PP-317', effective_state: 'approved', open_issue_count: 0 },
    ];
    const wrapper = mountQueue();

    expect(wrapper.find('a.review-link').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('Approve selected');
    expect(wrapper.find('[data-testid="review-table"]').attributes('onClick:row')).toBeUndefined();
  });

  it('keeps Retry available when the queue request failed', async () => {
    queue.error.value = new Error('Network unavailable');
    const wrapper = mountQueue();

    expect(wrapper.get('[role="alert"]').text()).toContain('Network unavailable');
    expect(wrapper.text()).not.toContain('No records are currently awaiting review.');
    expect(wrapper.text()).not.toContain('No records match the active filters.');
    await wrapper.get('[data-testid="retry-review-queue"]').trigger('click');
    expect(queue.retry).toHaveBeenCalledOnce();
  });

  it('distinguishes a truly empty queue from an empty filtered result', () => {
    const empty = mountQueue();
    expect(empty.text()).toContain('No records are currently awaiting review.');

    queue.hasFilters = computed(() => true);
    const filtered = mountQueue();
    expect(filtered.text()).toContain('No records match the active filters.');
    expect(filtered.text()).toContain('Clear filters');
  });

  it('keeps state and issue count in row slots for mobile cards', () => {
    queue.items.value = [
      { phenopacket_id: 'PP-318', effective_state: 'changes_requested', open_issue_count: 1 },
    ];

    const wrapper = mountQueue();

    expect(wrapper.text()).toContain('changes_requested');
    expect(wrapper.text()).toContain('1 open issue');
    expect(wrapper.get('.queue-row [aria-label]').attributes('aria-label')).toBe('1 open issue');
  });

  it('commits search only when the toolbar emits its debounced search event', async () => {
    const wrapper = mountQueue();

    await wrapper.get('[data-testid="search-input-event"]').trigger('click');
    expect(queue.search.value).toBe('');

    await wrapper.get('[data-testid="debounced-search-event"]').trigger('click');
    expect(queue.search.value).toBe('renal');
  });

  it.each([
    ['needs-review', 'No records are currently awaiting review.'],
    ['changes-requested', 'No records currently require changes.'],
    ['approved', 'No records are currently approved for publication.'],
    ['my-drafts', 'You have no draft records in the review queue.'],
  ])('renders tab-aware unfiltered empty copy for %s', (tab, expected) => {
    queue.tab.value = tab;

    const wrapper = mountQueue();

    expect(wrapper.text()).toContain(expected);
  });
});
