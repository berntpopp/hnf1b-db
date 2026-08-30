import { ref, unref, watch } from 'vue';

import { getReviewContext } from '@/api/domain/reviews';

function hasAuthoritativeIssueCount(value) {
  return (
    Number.isInteger(value?.discussion_summary?.open_blocking_issues) &&
    value.discussion_summary.open_blocking_issues >= 0
  );
}

function issueCountMessage(count) {
  return count === 1 ? '1 open blocking issue remains.' : `${count} open blocking issues remain.`;
}

/** Load one coherent, server-authoritative review workspace snapshot. */
export function useReviewContext(id) {
  const context = ref(null);
  const loading = ref(false);
  const error = ref(null);
  const conflict = ref(null);
  const liveMessage = ref('');
  let requestToken = 0;

  function invalidate() {
    requestToken += 1;
    context.value = null;
    loading.value = false;
    error.value = null;
    conflict.value = null;
    liveMessage.value = '';
  }

  watch(() => unref(id), invalidate, { flush: 'sync' });

  async function load({ announceIssueCount = false } = {}) {
    const token = ++requestToken;
    const recordId = unref(id);
    const previousCount = context.value?.discussion_summary?.open_blocking_issues;
    loading.value = true;
    error.value = null;

    try {
      const response = await getReviewContext(recordId);
      if (token !== requestToken) return null;
      const nextContext = response.data;
      if (!hasAuthoritativeIssueCount(nextContext)) {
        throw new Error('Review context does not include an authoritative open issue count.');
      }

      context.value = nextContext;
      if (
        announceIssueCount &&
        Number.isInteger(previousCount) &&
        previousCount !== nextContext.discussion_summary.open_blocking_issues
      ) {
        liveMessage.value = issueCountMessage(nextContext.discussion_summary.open_blocking_issues);
      }
      return nextContext;
    } catch (requestError) {
      if (token === requestToken) {
        context.value = null;
        error.value = requestError;
        window.logService?.error?.('Failed to fetch review context', {
          recordId,
          error: requestError?.message,
        });
      }
      return null;
    } finally {
      if (token === requestToken) loading.value = false;
    }
  }

  function reload() {
    return load({ announceIssueCount: true });
  }

  function markConflict(value) {
    conflict.value = value;
  }

  function clearConflict() {
    conflict.value = null;
  }

  return {
    context,
    loading,
    error,
    conflict,
    liveMessage,
    load,
    reload,
    markConflict,
    clearConflict,
    invalidate,
  };
}
