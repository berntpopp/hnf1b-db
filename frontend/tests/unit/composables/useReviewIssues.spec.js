import { ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { createComment, resolveComment, unresolveComment } = vi.hoisted(() => ({
  createComment: vi.fn(),
  resolveComment: vi.fn(),
  unresolveComment: vi.fn(),
}));

vi.mock('@/api/domain/comments', () => ({ createComment, resolveComment, unresolveComment }));

import { useReviewIssues } from '@/composables/useReviewIssues';

const RECORD_ID = '4c096c55-8f3e-48d3-a759-c57851f3aa31';
const issue = {
  id: 55,
  record_type: 'phenopacket',
  record_id: RECORD_ID,
  is_blocking_issue: true,
  review_revision_id: 42,
};

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

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

const mutationArguments = {
  create: [{ bodyMarkdown: 'A blocking issue.' }],
  resolve: [issue, { disposition: 'addressed', rationale: 'Addressed.' }],
  reopen: [issue, { rationale: 'Reopened.' }],
};

function mutation(review, operation) {
  return {
    create: review.createIssue,
    resolve: review.resolveIssue,
    reopen: review.reopenIssue,
  }[operation](...mutationArguments[operation]);
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

  it('resolves an issue from a prior submission in the active cycle then reloads', async () => {
    const { review, reload } = setup();
    const priorCandidateIssue = { ...issue, review_revision_id: 41 };

    await review.resolveIssue(priorCandidateIssue, {
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

  it.each([
    [{ ...issue, record_id: 'a51f4850-05d5-43d3-90e0-ca5c573ba284' }, 'record identity'],
    [{ ...issue, record_type: 'variant' }, 'record identity'],
    [{ ...issue, is_blocking_issue: false }, 'blocking issue'],
    [{ ...issue, review_revision_id: null }, 'review revision'],
    [{ ...issue, review_revision_id: 0 }, 'review revision'],
  ])('rejects an invalid issue DTO before transport', async (invalidIssue, message) => {
    const { review } = setup();

    await expect(
      review.resolveIssue(invalidIssue, { disposition: 'addressed', rationale: 'Done' })
    ).rejects.toThrow(message);
    expect(resolveComment).not.toHaveBeenCalled();
  });

  it('rejects an invalid disposition or blank rationale before transport', async () => {
    const { review } = setup();

    await expect(
      review.resolveIssue(issue, { disposition: 'deleted', rationale: 'Done' })
    ).rejects.toThrow('disposition');
    await expect(
      review.resolveIssue(issue, { disposition: 'addressed', rationale: '   ' })
    ).rejects.toThrow('rationale');
    expect(resolveComment).not.toHaveBeenCalled();
  });

  it('reopens an issue from a prior submission in the active cycle then reloads', async () => {
    const { review, reload } = setup();
    const priorCandidateIssue = { ...issue, review_revision_id: 41 };

    await review.reopenIssue(priorCandidateIssue, { rationale: 'The correction was removed.' });

    expect(unresolveComment).toHaveBeenCalledWith(55, {
      recordRevision: 11,
      rationale: 'The correction was removed.',
    });
    expect(reload).toHaveBeenCalledOnce();
  });

  it('accepts a 500-character resolve rationale and rejects 501 before transport', async () => {
    const { review, reload } = setup();
    const accepted = 'a'.repeat(500);

    await review.resolveIssue(issue, { disposition: 'addressed', rationale: accepted });

    expect(resolveComment).toHaveBeenCalledWith(55, {
      recordRevision: 11,
      disposition: 'addressed',
      rationale: accepted,
    });
    expect(reload).toHaveBeenCalledOnce();
    resolveComment.mockClear();

    await expect(
      review.resolveIssue(issue, { disposition: 'addressed', rationale: 'a'.repeat(501) })
    ).rejects.toThrow('500 characters');
    expect(resolveComment).not.toHaveBeenCalled();
  });

  it('accepts a 500-character reopen rationale and rejects 501 before transport', async () => {
    const { review, reload } = setup();
    const accepted = 'a'.repeat(500);

    await review.reopenIssue(issue, { rationale: accepted });

    expect(unresolveComment).toHaveBeenCalledWith(55, {
      recordRevision: 11,
      rationale: accepted,
    });
    expect(reload).toHaveBeenCalledOnce();
    unresolveComment.mockClear();

    await expect(review.reopenIssue(issue, { rationale: 'a'.repeat(501) })).rejects.toThrow(
      '500 characters'
    );
    expect(unresolveComment).not.toHaveBeenCalled();
  });

  it('keeps blocking issue creation at the 10,000-character contract', async () => {
    const { review } = setup();
    const accepted = 'a'.repeat(10_000);

    await review.createIssue({ bodyMarkdown: accepted });
    expect(createComment).toHaveBeenCalledWith(expect.objectContaining({ bodyMarkdown: accepted }));
    createComment.mockClear();

    await expect(review.createIssue({ bodyMarkdown: 'a'.repeat(10_001) })).rejects.toThrow(
      '10000 characters'
    );
    expect(createComment).not.toHaveBeenCalled();
  });

  it.each([
    ['create', createComment, { data: { id: 56 } }],
    ['resolve', resolveComment, { data: { ...issue, resolved_at: '2026-08-14T10:00:00Z' } }],
    ['reopen', unresolveComment, { data: { ...issue, resolved_at: null } }],
  ])('keeps duplicate %s mutations single-flight', async (operation, transport, response) => {
    const pending = deferred();
    transport.mockReturnValueOnce(pending.promise);
    const { review } = setup();

    const first = mutation(review, operation);
    await expect(mutation(review, operation)).rejects.toMatchObject({
      code: 'issue_mutation_in_progress',
    });
    expect(transport).toHaveBeenCalledOnce();

    pending.resolve(response);
    await first;
  });

  it.each([
    ['create', createComment, 'revision_mismatch'],
    ['resolve', resolveComment, 'review_revision_mismatch'],
    ['reopen', unresolveComment, 'review_closed'],
  ])(
    'maps %s 409 %s to explicit reload recovery without retry',
    async (operation, transport, code) => {
      const conflictError = Object.assign(new Error('Conflict'), {
        response: { status: 409, data: { detail: { code, message: 'Reload the issue state.' } } },
      });
      transport.mockRejectedValueOnce(conflictError);
      const { review, reload } = setup();

      await expect(mutation(review, operation)).rejects.toBe(conflictError);
      expect(review.conflict.value).toEqual({
        code,
        message: 'Reload the issue state.',
        reloadRequired: true,
      });
      await expect(mutation(review, operation)).rejects.toMatchObject({
        code: 'reload_required',
      });
      expect(transport).toHaveBeenCalledOnce();
      expect(reload).not.toHaveBeenCalled();

      await review.reloadConflict();
      expect(reload).toHaveBeenCalledOnce();
      expect(review.conflict.value).toBeNull();
    }
  );

  it('ignores a late old-record failure after a newer record succeeds', async () => {
    const recordId = ref(RECORD_ID);
    const recordRevision = ref(11);
    const candidateRevisionId = ref(42);
    const reload = vi.fn().mockResolvedValue({});
    const stale = deferred();
    createComment.mockReturnValueOnce(stale.promise).mockResolvedValueOnce({ data: { id: 99 } });
    const review = useReviewIssues({
      recordId,
      recordRevision,
      candidateRevisionId,
      reload,
    });

    const oldMutation = review.createIssue({ bodyMarkdown: 'Old record issue.' });
    recordId.value = '910eca1f-12b4-4294-8747-5987dad12253';
    recordRevision.value = 4;
    candidateRevisionId.value = 88;
    await review.createIssue({ bodyMarkdown: 'New record issue.' });
    stale.reject(
      Object.assign(new Error('Late old conflict'), {
        response: {
          status: 409,
          data: { detail: { code: 'revision_mismatch', message: 'Old stale state.' } },
        },
      })
    );
    await expect(oldMutation).rejects.toThrow('Late old conflict');

    expect(review.error.value).toBeNull();
    expect(review.conflict.value).toBeNull();
    expect(review.submitting.value).toBe(false);
    expect(reload).toHaveBeenCalledOnce();
  });
});
