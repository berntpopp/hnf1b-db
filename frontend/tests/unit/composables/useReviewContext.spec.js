import { beforeEach, describe, expect, it, vi } from 'vitest';

const { getReviewContext } = vi.hoisted(() => ({ getReviewContext: vi.fn() }));

vi.mock('@/api/domain/reviews', () => ({ getReviewContext }));

import { useReviewContext } from '@/composables/useReviewContext';

const contextFixture = (openBlockingIssues = 2) => ({
  record_id: '4c096c55-8f3e-48d3-a759-c57851f3aa31',
  record_revision: 11,
  candidate: { id: 42, content: { id: 'PP-1' } },
  baseline: null,
  semantic_changes: [],
  issues: [],
  discussion_summary: {
    total_comments: 2,
    ordinary_comments: 0,
    blocking_issues: 2,
    open_blocking_issues: openBlockingIssues,
  },
});

describe('useReviewContext', () => {
  beforeEach(() => vi.clearAllMocks());

  it('publishes one coherent backend review-context response', async () => {
    const payload = contextFixture();
    getReviewContext.mockResolvedValue({ data: payload });
    const review = useReviewContext('PP/1');

    const result = await review.load();

    expect(getReviewContext).toHaveBeenCalledWith('PP/1');
    expect(result).toBe(payload);
    expect(review.context.value).toEqual(payload);
    expect(review.loading.value).toBe(false);
    expect(review.error.value).toBeNull();
  });

  it('fails closed when the authoritative open issue count is unavailable', async () => {
    getReviewContext.mockResolvedValue({
      data: {
        ...contextFixture(),
        discussion_summary: { ...contextFixture().discussion_summary, open_blocking_issues: null },
      },
    });
    const review = useReviewContext('PP-1');

    const result = await review.load();

    expect(result).toBeNull();
    expect(review.context.value).toBeNull();
    expect(review.error.value).toBeInstanceOf(Error);
  });

  it('announces the authoritative changed issue count after reload', async () => {
    getReviewContext
      .mockResolvedValueOnce({ data: contextFixture(2) })
      .mockResolvedValueOnce({ data: contextFixture(1) });
    const review = useReviewContext('PP-1');
    await review.load();

    await review.reload();

    expect(review.liveMessage.value).toBe('1 open blocking issue remains.');
  });

  it('marks and clears a revision conflict explicitly', () => {
    const review = useReviewContext('PP-1');
    const conflict = { message: 'Candidate changed' };

    review.markConflict(conflict);
    expect(review.conflict.value).toEqual(conflict);
    review.clearConflict();
    expect(review.conflict.value).toBeNull();
  });

  it('ignores an out-of-order stale success after a newer context owns state', async () => {
    let resolveOlder;
    let resolveNewer;
    getReviewContext
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveOlder = resolve;
          })
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveNewer = resolve;
          })
      );
    const review = useReviewContext('PP-1');
    const older = review.load();
    const newer = review.load();
    const newestPayload = { ...contextFixture(0), record_revision: 12 };

    resolveNewer({ data: newestPayload });
    await newer;
    resolveOlder({ data: { ...contextFixture(2), record_revision: 11 } });
    await older;

    expect(review.context.value).toEqual(newestPayload);
    expect(review.error.value).toBeNull();
  });

  it('ignores an out-of-order stale error after a newer context owns state', async () => {
    let rejectOlder;
    let resolveNewer;
    getReviewContext
      .mockImplementationOnce(
        () =>
          new Promise((_resolve, reject) => {
            rejectOlder = reject;
          })
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveNewer = resolve;
          })
      );
    const review = useReviewContext('PP-1');
    const older = review.load();
    const newer = review.load();
    const newestPayload = { ...contextFixture(0), record_revision: 12 };

    resolveNewer({ data: newestPayload });
    await newer;
    rejectOlder(new Error('stale request failed'));
    await older;

    expect(review.context.value).toEqual(newestPayload);
    expect(review.error.value).toBeNull();
  });
});
