import { ref, unref } from 'vue';

import { createComment, resolveComment, unresolveComment } from '@/api/domain/comments';

const RESOLUTION_DISPOSITIONS = new Set([
  'addressed',
  'accepted_with_rationale',
  'retracted',
  'superseded',
]);

function requiredText(value, label) {
  const text = typeof value === 'string' ? value.trim() : '';
  if (!text) throw new Error(`${label} is required.`);
  return text;
}

/** Mutate candidate-bound blocking issues through the typed comment transport. */
export function useReviewIssues({ recordId, recordRevision, candidateRevisionId, reload }) {
  const submitting = ref(false);
  const error = ref(null);

  function assertCandidateIssue(issue) {
    if (!issue || issue.review_revision_id !== unref(candidateRevisionId)) {
      throw new Error('The issue does not belong to the current candidate revision.');
    }
  }

  async function mutate(operation) {
    submitting.value = true;
    error.value = null;
    try {
      const response = await operation();
      await reload();
      return response.data;
    } catch (mutationError) {
      error.value = mutationError;
      window.logService?.error?.('Review issue mutation failed', {
        recordId: unref(recordId),
        error: mutationError?.message,
      });
      throw mutationError;
    } finally {
      submitting.value = false;
    }
  }

  async function createIssue({ bodyMarkdown, mentionUserIds = [] }) {
    const body = requiredText(bodyMarkdown, 'Issue body');
    return await mutate(() =>
      createComment({
        recordType: 'phenopacket',
        recordId: unref(recordId),
        bodyMarkdown: body,
        mentionUserIds,
        recordRevision: unref(recordRevision),
        reviewRevisionId: unref(candidateRevisionId),
      })
    );
  }

  async function resolveIssue(issue, { disposition, rationale }) {
    assertCandidateIssue(issue);
    if (!RESOLUTION_DISPOSITIONS.has(disposition)) {
      throw new Error('A supported issue disposition is required.');
    }
    const evidence = requiredText(rationale, 'Resolution rationale');
    return await mutate(() =>
      resolveComment(issue.id, {
        recordRevision: unref(recordRevision),
        disposition,
        rationale: evidence,
      })
    );
  }

  async function reopenIssue(issue, { rationale }) {
    assertCandidateIssue(issue);
    const evidence = requiredText(rationale, 'Reopen rationale');
    return await mutate(() =>
      unresolveComment(issue.id, {
        recordRevision: unref(recordRevision),
        rationale: evidence,
      })
    );
  }

  return { submitting, error, createIssue, resolveIssue, reopenIssue };
}
