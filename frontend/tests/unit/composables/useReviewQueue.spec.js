import { effectScope, nextTick } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { getReviewQueue, mockReplace, mockRoute } = vi.hoisted(() => ({
  getReviewQueue: vi.fn(),
  mockReplace: vi.fn(() => Promise.resolve()),
  mockRoute: { query: {} },
}));

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  useRouter: () => ({ replace: mockReplace }),
}));

vi.mock('@/api/domain/reviews', () => ({ getReviewQueue }));

import { useReviewQueue } from '@/composables/useReviewQueue';

const row = (id = 'new') => ({
  phenopacket_id: id,
  physical_state: 'published',
  effective_state: 'in_review',
});

const response = (items = [row()], meta = {}) => ({
  data: {
    data: items,
    meta: { page_number: 1, page_size: 25, total: items.length, total_pages: 1, ...meta },
  },
});

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

function createQueue() {
  const scope = effectScope();
  const state = scope.run(() => useReviewQueue());
  return { scope, state };
}

describe('useReviewQueue', () => {
  beforeEach(() => {
    mockRoute.query = {};
    mockReplace.mockClear();
    getReviewQueue.mockReset();
    getReviewQueue.mockResolvedValue(response());
  });

  it('hydrates queue controls from a shareable URL and sends the exact server filters', async () => {
    mockRoute.query = {
      page: '3',
      pageSize: '50',
      sort: '-submitted_at',
      q: 'renal cysts',
      tab: 'changes-requested',
      eligibility: 'reviewable_by_me',
      issues: 'open',
    };

    const { scope, state } = createQueue();
    await flush();

    expect(state.page.value).toBe(3);
    expect(state.pageSize.value).toBe(50);
    expect(state.sort.value).toBe('-submitted_at');
    expect(state.search.value).toBe('renal cysts');
    expect(state.tab.value).toBe('changes-requested');
    expect(getReviewQueue).toHaveBeenLastCalledWith({
      pageNumber: 3,
      pageSize: 50,
      sort: '-submitted_at',
      q: 'renal cysts',
      state: 'changes_requested',
      eligibility: 'reviewable_by_me',
      issues: 'open',
    });
    scope.stop();
  });

  it.each([
    ['needs-review', { state: 'in_review' }],
    ['changes-requested', { state: 'changes_requested' }],
    ['approved', { state: 'approved' }],
    ['my-drafts', { state: 'draft', owner: 'mine' }],
  ])('maps %s to its exact server-side queue filters', async (tab, expected) => {
    const { scope, state } = createQueue();
    await flush();
    getReviewQueue.mockClear();

    state.setTab(tab);
    await state.load();

    expect(getReviewQueue).toHaveBeenLastCalledWith({ pageNumber: 1, pageSize: 25, ...expected });
    scope.stop();
  });

  it('resets the URL page before loading when a search, tab, or filter changes', async () => {
    mockRoute.query = { page: '4' };
    const { scope, state } = createQueue();
    await flush();
    getReviewQueue.mockClear();

    state.search.value = 'HNF1B';
    await nextTick();
    await flush();
    expect(state.page.value).toBe(1);
    expect(getReviewQueue).toHaveBeenLastCalledWith({
      pageNumber: 1,
      pageSize: 25,
      state: 'in_review',
      q: 'HNF1B',
    });

    state.eligibility.value = 'reviewable_by_me';
    await flush();
    expect(getReviewQueue).toHaveBeenLastCalledWith({
      pageNumber: 1,
      pageSize: 25,
      state: 'in_review',
      q: 'HNF1B',
      eligibility: 'reviewable_by_me',
    });

    state.page.value = 3;
    await flush();
    state.setTab('changes-requested');
    await flush();
    expect(state.page.value).toBe(1);
    expect(getReviewQueue).toHaveBeenLastCalledWith({
      pageNumber: 1,
      pageSize: 25,
      state: 'changes_requested',
      q: 'HNF1B',
      eligibility: 'reviewable_by_me',
    });
    scope.stop();
  });

  it('clears search and auxiliary filters without leaving the active approved tab', async () => {
    mockRoute.query = {
      page: '3',
      tab: 'approved',
      q: 'HNF1B',
      eligibility: 'reviewable_by_me',
      issues: 'open',
    };
    const { scope, state } = createQueue();
    await flush();
    getReviewQueue.mockClear();

    state.clearFilters();
    await flush();

    expect(state.tab.value).toBe('approved');
    expect(state.search.value).toBe('');
    expect(state.eligibility.value).toBe('all');
    expect(state.issues.value).toBe('all');
    expect(state.page.value).toBe(1);
    expect(getReviewQueue).toHaveBeenLastCalledWith({
      pageNumber: 1,
      pageSize: 25,
      state: 'approved',
    });
    scope.stop();
  });

  it('keeps backend rows and backend pagination totals without local transformation', async () => {
    getReviewQueue.mockResolvedValueOnce(
      response([row('PP-1'), row('PP-2')], { total: 41, total_pages: 3 })
    );
    const { scope, state } = createQueue();
    await flush();

    expect(state.items.value).toEqual([row('PP-1'), row('PP-2')]);
    expect(state.meta.value).toMatchObject({ total: 41, total_pages: 3 });
    scope.stop();
  });

  it('does not let an older response overwrite a newer queue result', async () => {
    let resolveFirst;
    let resolveSecond;
    getReviewQueue
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          })
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveSecond = resolve;
          })
      );
    const { scope, state } = createQueue();
    await nextTick();

    state.setTab('approved');
    await nextTick();
    resolveSecond(response([row('new')], { total: 1 }));
    await flush();
    resolveFirst(response([row('stale')], { total: 99 }));
    await flush();

    expect(state.items.value).toEqual([row('new')]);
    expect(state.meta.value.total).toBe(1);
    scope.stop();
  });

  it('keeps the latest request error available for retry', async () => {
    const error = new Error('Queue unavailable');
    getReviewQueue.mockRejectedValueOnce(error).mockResolvedValueOnce(response([row('recovered')]));
    const { scope, state } = createQueue();
    await flush();

    expect(state.error.value).toBe(error);
    await state.retry();

    expect(state.error.value).toBeNull();
    expect(state.items.value).toEqual([row('recovered')]);
    scope.stop();
  });
});
