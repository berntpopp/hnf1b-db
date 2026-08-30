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
    { action: 'publish', allowed: true, blocked_by: [] },
    { action: 'withdraw', allowed: true, blocked_by: [] },
  ],
  ...overrides,
});

function setup(overrides = {}) {
  const context = ref(contextFixture(overrides));
  const reload = vi.fn().mockImplementation(async () => {
    const next = { ...context.value, record_revision: context.value.record_revision + 1 };
    context.value = next;
    return next;
  });
  const onCompleted = vi.fn();
  const review = useReviewActions(ref('PP-route'), context, { reload, onCompleted });
  return { context, reload, onCompleted, review };
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
    ['requestChanges', 'request_changes', 'changes_requested'],
    ['reopenApproved', 'request_changes', 'changes_requested'],
    ['withdraw', 'withdraw', 'draft'],
  ])('uses the loaded record revision for %s', async (method, _capability, toState) => {
    const { review } = setup();

    await review[method]({ rationale: 'A recorded decision rationale.' });

    expect(transitionPhenopacket).toHaveBeenCalledWith(
      'PP-loaded',
      toState,
      'A recorded decision rationale.',
      11,
      {}
    );
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
});
