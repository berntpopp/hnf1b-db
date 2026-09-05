import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockPost } = vi.hoisted(() => ({
  mockPost: vi.fn(),
}));

vi.mock('@/api/transport', () => ({
  apiClient: { post: mockPost },
}));

import { createComment, resolveComment, unresolveComment } from '@/api/domain/comments';

describe('comments API domain helper review issue serialization', () => {
  beforeEach(() => vi.clearAllMocks());

  it('creates a revision-bound blocking review issue', async () => {
    await createComment({
      recordType: 'phenopacket',
      recordId: '4c096c55-8f3e-48d3-a759-c57851f3aa31',
      bodyMarkdown: 'Variant evidence needs correction.',
      mentionUserIds: [7, 8],
      recordRevision: 11,
      reviewRevisionId: 42,
    });

    expect(mockPost).toHaveBeenCalledWith('/comments', {
      record_type: 'phenopacket',
      record_id: '4c096c55-8f3e-48d3-a759-c57851f3aa31',
      body_markdown: 'Variant evidence needs correction.',
      mention_user_ids: [7, 8],
      record_revision: 11,
      review_revision_id: 42,
    });
  });

  it('omits review issue fields for ordinary comments', async () => {
    await createComment({
      recordType: 'phenopacket',
      recordId: '4c096c55-8f3e-48d3-a759-c57851f3aa31',
      bodyMarkdown: 'General note.',
    });

    expect(mockPost).toHaveBeenCalledWith('/comments', {
      record_type: 'phenopacket',
      record_id: '4c096c55-8f3e-48d3-a759-c57851f3aa31',
      body_markdown: 'General note.',
      mention_user_ids: [],
    });
  });

  it('serializes typed issue resolution evidence', async () => {
    await resolveComment(55, {
      recordRevision: 12,
      disposition: 'addressed',
      rationale: 'Candidate snapshot now includes the corrected evidence.',
    });

    expect(mockPost).toHaveBeenCalledWith('/comments/55/resolve', {
      record_revision: 12,
      disposition: 'addressed',
      rationale: 'Candidate snapshot now includes the corrected evidence.',
    });
  });

  it('serializes typed issue reopen evidence', async () => {
    await unresolveComment(55, {
      recordRevision: 13,
      rationale: 'The follow-up edit removed the correction.',
    });

    expect(mockPost).toHaveBeenCalledWith('/comments/55/unresolve', {
      record_revision: 13,
      rationale: 'The follow-up edit removed the correction.',
    });
  });

  it('keeps ordinary resolution bodyless', async () => {
    await resolveComment(56);

    expect(mockPost).toHaveBeenCalledWith('/comments/56/resolve');
  });
});
