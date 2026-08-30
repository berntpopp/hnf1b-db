import { beforeEach, describe, expect, it, vi } from 'vitest';

const { createComment, resolveComment, unresolveComment } = vi.hoisted(() => ({
  createComment: vi.fn(),
  resolveComment: vi.fn(),
  unresolveComment: vi.fn(),
}));

vi.mock('@/api/domain/comments', () => ({ createComment, resolveComment, unresolveComment }));

import { useReviewIssues } from '@/composables/useReviewIssues';

const RECORD_ID = '4c096c55-8f3e-48d3-a759-c57851f3aa31';
const issue = { id: 55, review_revision_id: 42 };

function setup() {
  const reload = vi.fn().mockResolvedValue({ discussion_summary: { open_blocking_issues: 1 } });
  return {
    reload,
    review: useReviewIssues({
      recordId: RECORD_ID,
      recordRevision: 11,
      candidateRevisionId: 42,
      reload,
    }),
  };
}

describe('useReviewIssues', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    createComment.mockResolvedValue({ data: { id: 56 } });
    resolveComment.mockResolvedValue({ data: { ...issue, resolved_at: '2026-08-14T10:00:00Z' } });
    unresolveComment.mockResolvedValue({ data: { ...issue, resolved_at: null } });
  });

  it('creates an issue bound to the exact record and candidate revisions then reloads', async () => {
    const { review, reload } = setup();

    await review.createIssue({ bodyMarkdown: 'Variant evidence needs correction.' });

    expect(createComment).toHaveBeenCalledWith({
      recordType: 'phenopacket',
      recordId: RECORD_ID,
      bodyMarkdown: 'Variant evidence needs correction.',
      mentionUserIds: [],
      recordRevision: 11,
      reviewRevisionId: 42,
    });
    expect(reload).toHaveBeenCalledOnce();
  });

  it('resolves only the exact candidate issue with an allowed disposition and rationale', async () => {
    const { review, reload } = setup();

    await review.resolveIssue(issue, {
      disposition: 'accepted_with_rationale',
      rationale: 'Evidence is sufficient for this candidate.',
    });

    expect(resolveComment).toHaveBeenCalledWith(55, {
      recordRevision: 11,
      disposition: 'accepted_with_rationale',
      rationale: 'Evidence is sufficient for this candidate.',
    });
    expect(reload).toHaveBeenCalledOnce();
  });

  it('rejects a stale candidate issue, invalid disposition, or blank rationale', async () => {
    const { review } = setup();

    await expect(
      review.resolveIssue(
        { ...issue, review_revision_id: 41 },
        { disposition: 'addressed', rationale: 'Done' }
      )
    ).rejects.toThrow('candidate revision');
    await expect(
      review.resolveIssue(issue, { disposition: 'deleted', rationale: 'Done' })
    ).rejects.toThrow('disposition');
    await expect(
      review.resolveIssue(issue, { disposition: 'addressed', rationale: '   ' })
    ).rejects.toThrow('rationale');
    expect(resolveComment).not.toHaveBeenCalled();
  });

  it('reopens the exact candidate issue with rationale then reloads', async () => {
    const { review, reload } = setup();

    await review.reopenIssue(issue, { rationale: 'The correction was removed.' });

    expect(unresolveComment).toHaveBeenCalledWith(55, {
      recordRevision: 11,
      rationale: 'The correction was removed.',
    });
    expect(reload).toHaveBeenCalledOnce();
  });
});
