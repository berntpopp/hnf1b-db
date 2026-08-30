import { ref, unref } from 'vue';

import { createComment, resolveComment, unresolveComment } from '@/api/domain/comments';

const RESOLUTION_DISPOSITIONS = new Set([
  'addressed',
  'accepted_with_rationale',
  'retracted',
  'superseded',
]);
const ISSUE_BODY_MAX_LENGTH = 10_000;
const RATIONALE_MAX_LENGTH = 500;

function requiredText(value, label, maxLength) {
  const text = typeof value === 'string' ? value.trim() : '';
  if (!text) throw new Error(`${label} is required.`);
  if (text.length > maxLength) {
    throw new Error(`${label} must not exceed ${maxLength} characters.`);
  }
  return text;
}

/** Mutate candidate-bound blocking issues through the typed comment transport. */
export function useReviewIssues({ recordId, recordRevision, candidateRevisionId, reload }) {
  const submitting = ref(false);
  const error = ref(null);

  function assertActionableIssue(issue) {
    if (!issue || issue.record_type !== 'phenopacket' || issue.record_id !== unref(recordId)) {
      throw new Error('The issue record identity does not match the review context.');
    }
    if (issue.is_blocking_issue !== true) {
      throw new Error('The comment is not a blocking issue.');
    }
    if (!Number.isInteger(issue.review_revision_id) || issue.review_revision_id <= 0) {
      throw new Error('The issue review revision is invalid.');
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
    const body = requiredText(bodyMarkdown, 'Issue body', ISSUE_BODY_MAX_LENGTH);
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
    assertActionableIssue(issue);
    if (!RESOLUTION_DISPOSITIONS.has(disposition)) {
      throw new Error('A supported issue disposition is required.');
    }
    const evidence = requiredText(rationale, 'Resolution rationale', RATIONALE_MAX_LENGTH);
    return await mutate(() =>
      resolveComment(issue.id, {
        recordRevision: unref(recordRevision),
        disposition,
        rationale: evidence,
      })
    );
  }

  async function reopenIssue(issue, { rationale }) {
    assertActionableIssue(issue);
    const evidence = requiredText(rationale, 'Reopen rationale', RATIONALE_MAX_LENGTH);
    return await mutate(() =>
      unresolveComment(issue.id, {
        recordRevision: unref(recordRevision),
        rationale: evidence,
      })
    );
  }

  return { submitting, error, createIssue, resolveIssue, reopenIssue };
}
