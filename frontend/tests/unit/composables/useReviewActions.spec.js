import { ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { transitionPhenopacket } = vi.hoisted(() => ({ transitionPhenopacket: vi.fn() }));

vi.mock('@/api/domain/phenopackets', () => ({ transitionPhenopacket }));

import { useReviewActions } from '@/composables/useReviewActions';

const candidateDigest = `sha256:${'a'.repeat(64)}`;
const approvedDigest = `sha256:${'b'.repeat(64)}`;

const contextFixture = (overrides = {}) => ({
  phenopacket_id: 'PP-loaded',
  record_revision: 11,
  effective_state: 'in_review',
  candidate: { id: 42, content_sha256: candidateDigest },
  approved: { id: 43, content_sha256: approvedDigest },
  discussion_summary: { open_blocking_issues: 0 },
  capabilities: [
    { action: 'request_changes', allowed: true, blocked_by: [] },
    { action: 'approve', allowed: true, blocked_by: [] },
  ],
  ...overrides,
});

function setup(overrides = {}) {
  const routeId = ref('PP-route');
  const context = ref(contextFixture(overrides));
  const reload = vi.fn().mockImplementation(async () => {
    const next = { ...context.value, record_revision: context.value.record_revision + 1 };
    context.value = next;
    return next;
  });
  const onCompleted = vi.fn();
  const review = useReviewActions(routeId, context, { reload, onCompleted });
  return { routeId, context, reload, onCompleted, review };
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

describe('useReviewActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    transitionPhenopacket.mockResolvedValue({ data: { revision: { id: 44 } } });
  });

  it('approves only the loaded candidate identity with rationale and both attestations', async () => {
    const { review, reload, onCompleted } = setup({
      candidate_revision_id: 999,
      candidate_content_sha256: `sha256:${'f'.repeat(64)}`,
    });

    await review.approve({
      rationale: '  Independently verified against the candidate.  ',
      independentReview: true,
      noUnmanagedConflict: true,
    });

    expect(transitionPhenopacket).toHaveBeenCalledWith(
      'PP-loaded',
      'approved',
      'Independently verified against the candidate.',
      11,
      {
        candidateRevisionId: 42,
        candidateContentSha256: candidateDigest,
        attestation: { independentReview: true, noUnmanagedConflict: true },
      }
    );
    expect(reload).toHaveBeenCalledOnce();
    expect(onCompleted).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'approve', result: { revision: { id: 44 } } })
    );
  });

  it('publishes only the loaded approval identity when the server capability allows it', async () => {
    const { review } = setup({
      effective_state: 'approved',
      capabilities: [
        { action: 'request_changes', allowed: true, blocked_by: [] },
        { action: 'publish', allowed: true, blocked_by: [] },
      ],
      approved_revision_id: 999,
      approved_content_sha256: `sha256:${'f'.repeat(64)}`,
    });

    await review.publish({ rationale: 'Publish the independently approved snapshot.' });

    expect(transitionPhenopacket).toHaveBeenCalledWith(
      'PP-loaded',
      'published',
      'Publish the independently approved snapshot.',
      11,
      { approvedRevisionId: 43, approvedContentSha256: approvedDigest }
    );
  });

  it.each([
    ['requestChanges', 'changes_requested', {}],
    [
      'reopenApproved',
      'changes_requested',
      {
        effective_state: 'approved',
        capabilities: [{ action: 'request_changes', allowed: true, blocked_by: [] }],
      },
    ],
    [
      'withdraw',
      'draft',
      {
        capabilities: [
          {
            action: 'request_changes',
            allowed: false,
            blocked_by: ['self_review_forbidden'],
          },
          { action: 'approve', allowed: false, blocked_by: ['self_review_forbidden'] },
          { action: 'withdraw', allowed: true, blocked_by: [] },
        ],
      },
    ],
  ])('uses the loaded record revision for %s', async (method, toState, overrides) => {
    const { review } = setup(overrides);

    await review[method]({ rationale: 'A recorded decision rationale.' });

    expect(transitionPhenopacket).toHaveBeenCalledWith(
      'PP-loaded',
      toState,
      'A recorded decision rationale.',
      11,
      {}
    );
  });

  it('fails closed before a second transport while a decision is submitting', async () => {
    let resolveTransition;
    transitionPhenopacket.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveTransition = resolve;
        })
    );
    const { review } = setup();
    const first = review.approve({
      rationale: 'Independent review complete.',
      independentReview: true,
      noUnmanagedConflict: true,
    });

    expect(review.submitting.value).toBe(true);
    await expect(
      review.requestChanges({ rationale: 'A second concurrent decision.' })
    ).rejects.toMatchObject({ code: 'decision_in_progress' });
    expect(transitionPhenopacket).toHaveBeenCalledOnce();

    resolveTransition({ data: { revision: { id: 44 } } });
    await first;
  });

  it('fails closed when issue status is unknown or open even if approval is misreported allowed', async () => {
    const unknown = setup({ discussion_summary: { open_blocking_issues: null } });
    await expect(
      unknown.review.approve({
        rationale: 'Review complete.',
        independentReview: true,
        noUnmanagedConflict: true,
      })
    ).rejects.toThrow('issue status');

    const open = setup({ discussion_summary: { open_blocking_issues: 2 } });
    await expect(
      open.review.approve({
        rationale: 'Review complete.',
        independentReview: true,
        noUnmanagedConflict: true,
      })
    ).rejects.toThrow('2 unresolved blocking issues');

    expect(transitionPhenopacket).not.toHaveBeenCalled();
  });

  it('uses the server capability blocker and validates the complete attestation before transport', async () => {
    const { review } = setup({
      capabilities: [{ action: 'approve', allowed: false, blocked_by: ['reviewer_contributed'] }],
    });

    await expect(
      review.approve({
        rationale: 'Review complete.',
        independentReview: true,
        noUnmanagedConflict: true,
      })
    ).rejects.toMatchObject({ code: 'reviewer_contributed' });

    const allowed = setup();
    await expect(
      allowed.review.approve({
        rationale: 'Review complete.',
        independentReview: true,
        noUnmanagedConflict: false,
      })
    ).rejects.toThrow('attestations');
    expect(transitionPhenopacket).not.toHaveBeenCalled();
  });

  it.each(['revision_mismatch', 'review_revision_mismatch'])(
    'maps %s to a reload-required conflict and never retries blindly',
    async (code) => {
      const requestError = Object.assign(new Error('Conflict'), {
        response: { status: 409, data: { detail: { code, message: 'Snapshot changed.' } } },
      });
      transitionPhenopacket.mockRejectedValueOnce(requestError);
      const { review, reload, onCompleted } = setup();
      const approval = {
        rationale: 'Independent review complete.',
        independentReview: true,
        noUnmanagedConflict: true,
      };

      await expect(review.approve(approval)).rejects.toBe(requestError);

      expect(review.conflict.value).toEqual({
        code,
        message: 'Snapshot changed.',
        reloadRequired: true,
      });
      expect(reload).not.toHaveBeenCalled();
      expect(onCompleted).not.toHaveBeenCalled();

      await expect(review.approve(approval)).rejects.toMatchObject({ code: 'reload_required' });
      expect(transitionPhenopacket).toHaveBeenCalledOnce();
    }
  );

  it('clears a conflict only when reload replaces the coherent context snapshot', async () => {
    const { context, review } = setup();
    transitionPhenopacket.mockRejectedValueOnce(
      Object.assign(new Error('Stale'), {
        response: {
          status: 409,
          data: { detail: { code: 'revision_mismatch', message: 'Reload.' } },
        },
      })
    );

    await expect(
      review.approve({
        rationale: 'Independent review complete.',
        independentReview: true,
        noUnmanagedConflict: true,
      })
    ).rejects.toThrow('Stale');
    expect(review.conflict.value).not.toBeNull();

    context.value = { ...context.value, record_revision: 12 };
    await Promise.resolve();

    expect(review.conflict.value).toBeNull();
  });

  it('invalidates an A decision synchronously and prevents its late failure from owning B', async () => {
    const stale = deferred();
    transitionPhenopacket
      .mockReturnValueOnce(stale.promise)
      .mockResolvedValueOnce({ data: { revision: { id: 90 } } });
    const { routeId, context, review, reload, onCompleted } = setup();

    const oldDecision = review.requestChanges({ rationale: 'Record A needs changes.' });
    routeId.value = 'PP-B';
    context.value = contextFixture({
      phenopacket_id: 'PP-B',
      record_revision: 3,
    });

    expect(review.submitting.value).toBe(false);
    expect(review.pendingAction.value).toBeNull();
    expect(review.error.value).toBeNull();
    expect(review.conflict.value).toBeNull();

    await review.requestChanges({ rationale: 'Record B needs changes.' });
    expect(transitionPhenopacket).toHaveBeenNthCalledWith(
      2,
      'PP-B',
      'changes_requested',
      'Record B needs changes.',
      3,
      {}
    );
    expect(reload).toHaveBeenCalledOnce();
    expect(onCompleted).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'request_changes', recordId: 'PP-B' })
    );

    stale.reject(
      Object.assign(new Error('Late A conflict'), {
        response: {
          status: 409,
          data: { detail: { code: 'revision_mismatch', message: 'Stale A.' } },
        },
      })
    );
    await expect(oldDecision).rejects.toThrow('Late A conflict');
    expect(review.error.value).toBeNull();
    expect(review.conflict.value).toBeNull();
    expect(review.submitting.value).toBe(false);
  });
});
