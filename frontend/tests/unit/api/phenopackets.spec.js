import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDelete = vi.fn();
const mockGet = vi.fn();
const mockPost = vi.fn();

vi.mock('@/api/transport', () => ({
  apiClient: {
    delete: mockDelete,
    get: mockGet,
    post: mockPost,
  },
}));

describe('phenopackets API domain helper', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends revision and change_reason in the delete request body', async () => {
    const { deletePhenopacket } = await import('@/api/domain/phenopackets');

    await deletePhenopacket('PP-1', 7, 'cleanup duplicate record');

    expect(mockDelete).toHaveBeenCalledWith('/phenopackets/PP-1', {
      data: {
        revision: 7,
        change_reason: 'cleanup duplicate record',
      },
    });
  });

  it('requests an encoded server-redacted GA4GH export', async () => {
    const { exportPhenopacket } = await import('@/api/domain/phenopackets');

    await exportPhenopacket('PP/1');

    expect(mockGet).toHaveBeenCalledWith('/phenopackets/PP%2F1/export', {
      params: { representation: 'ga4gh' },
    });
  });

  it('serializes candidate snapshot approval fields and attestation', async () => {
    const { transitionPhenopacket } = await import('@/api/domain/phenopackets');

    await transitionPhenopacket('PP/1', 'approved', 'Independent review complete.', 9, {
      candidateRevisionId: 42,
      candidateContentSha256: `sha256:${'a'.repeat(64)}`,
      attestation: {
        independentReview: true,
        noUnmanagedConflict: true,
      },
    });

    expect(mockPost).toHaveBeenCalledWith('/phenopackets/PP%2F1/transitions', {
      to_state: 'approved',
      reason: 'Independent review complete.',
      revision: 9,
      candidate_revision_id: 42,
      candidate_content_sha256: `sha256:${'a'.repeat(64)}`,
      attestation: {
        independent_review: true,
        no_unmanaged_conflict: true,
      },
    });
  });

  it('serializes approved snapshot publication fields', async () => {
    const { transitionPhenopacket } = await import('@/api/domain/phenopackets');

    await transitionPhenopacket('PP-1', 'published', 'Publish approved record.', 10, {
      approvedRevisionId: 43,
      approvedContentSha256: `sha256:${'b'.repeat(64)}`,
    });

    expect(mockPost).toHaveBeenCalledWith('/phenopackets/PP-1/transitions', {
      to_state: 'published',
      reason: 'Publish approved record.',
      revision: 10,
      approved_revision_id: 43,
      approved_content_sha256: `sha256:${'b'.repeat(64)}`,
    });
  });

  it('omits irrelevant snapshot fields for ordinary transitions', async () => {
    const { transitionPhenopacket } = await import('@/api/domain/phenopackets');

    await transitionPhenopacket('PP-1', 'changes_requested', 'Needs one correction.', 11, {
      candidateRevisionId: 42,
      candidateContentSha256: `sha256:${'a'.repeat(64)}`,
      approvedRevisionId: 43,
      approvedContentSha256: `sha256:${'b'.repeat(64)}`,
      attestation: {
        independentReview: true,
        noUnmanagedConflict: true,
      },
    });

    expect(mockPost).toHaveBeenCalledWith('/phenopackets/PP-1/transitions', {
      to_state: 'changes_requested',
      reason: 'Needs one correction.',
      revision: 11,
    });
  });
});
