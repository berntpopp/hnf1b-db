import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockGet } = vi.hoisted(() => ({
  mockGet: vi.fn(),
}));

vi.mock('@/api/transport', () => ({
  apiClient: { get: mockGet },
}));

import { getReviewContext, getReviewQueue } from '@/api/domain/reviews';

describe('reviews API domain helper', () => {
  beforeEach(() => vi.clearAllMocks());

  it('serializes every server-driven review queue parameter alias', async () => {
    await getReviewQueue({
      pageNumber: 3,
      pageSize: 50,
      state: 'changes_requested',
      owner: 'mine',
      eligibility: 'reviewable_by_me',
      issues: 'open',
      q: 'renal cysts',
      sort: '-submitted_at,subject_label',
    });

    expect(mockGet).toHaveBeenCalledWith('/phenopackets/review-queue', {
      params: {
        'page[number]': 3,
        'page[size]': 50,
        'filter[state]': 'changes_requested',
        'filter[owner]': 'mine',
        'filter[eligibility]': 'reviewable_by_me',
        'filter[issues]': 'open',
        q: 'renal cysts',
        sort: '-submitted_at,subject_label',
      },
    });
  });

  it('omits queue filters that the caller did not provide', async () => {
    await getReviewQueue({ pageNumber: 1, pageSize: 25 });

    expect(mockGet).toHaveBeenCalledWith('/phenopackets/review-queue', {
      params: {
        'page[number]': 1,
        'page[size]': 25,
      },
    });
  });

  it('requests an encoded review context record id', async () => {
    await getReviewContext('PP/317 candidate');

    expect(mockGet).toHaveBeenCalledWith('/phenopackets/PP%2F317%20candidate/review-context');
  });
});
