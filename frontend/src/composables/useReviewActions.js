import { ref, unref, watch } from 'vue';

import { transitionPhenopacket } from '@/api/domain/phenopackets';

const RATIONALE_MAX_LENGTH = 500;
const SNAPSHOT_DIGEST = /^sha256:[0-9a-f]{64}$/;
const CONFLICT_CODES = new Set(['revision_mismatch', 'review_revision_mismatch']);

function requiredRationale(value) {
  const rationale = typeof value === 'string' ? value.trim() : '';
  if (!rationale) throw new Error('A decision rationale is required.');
  if (rationale.length > RATIONALE_MAX_LENGTH) {
    throw new Error(`Decision rationale must not exceed ${RATIONALE_MAX_LENGTH} characters.`);
  }
  return rationale;
}

function requireCapability(context, action) {
  const capability = context.capabilities?.find((item) => item.action === action);
  if (!capability || !capability.allowed) {
    const code = capability?.blocked_by?.[0] || 'review_closed';
    throw Object.assign(new Error(`Review action is unavailable: ${code}.`), { code });
  }
}

function requireSnapshot(snapshot, label) {
  if (
    !Number.isInteger(snapshot?.id) ||
    snapshot.id <= 0 ||
    !SNAPSHOT_DIGEST.test(snapshot?.content_sha256 || '')
  ) {
    throw new Error(`The loaded ${label} identity is unavailable. Reload the review context.`);
  }
  return { id: snapshot.id, digest: snapshot.content_sha256 };
}

function requireContext(context) {
  if (
    !context ||
    typeof context.phenopacket_id !== 'string' ||
    !context.phenopacket_id ||
    !Number.isInteger(context.record_revision) ||
    context.record_revision < 0
  ) {
    throw new Error('A coherent loaded review context is required.');
  }
  return context;
}

function conflictDetail(error) {
  const detail = error?.response?.data?.detail;
  const code = detail?.code;
  if (error?.response?.status !== 409 || !CONFLICT_CODES.has(code)) return null;
  return {
    code,
    message:
      (typeof detail?.message === 'string' && detail.message) ||
      'The review snapshot changed. Reload before making another decision.',
    reloadRequired: true,
  };
}

/** Execute review decisions against one coherent, server-loaded snapshot. */
export function useReviewActions(id, contextRef, { reload, onCompleted } = {}) {
  const pendingAction = ref(null);
  const submitting = ref(false);
  const error = ref(null);
  const conflict = ref(null);

  watch(
    () => unref(contextRef),
    (next, previous) => {
      if (next !== previous) {
        conflict.value = null;
        error.value = null;
      }
    }
  );

  function assertReady(action) {
    if (conflict.value) {
      throw Object.assign(new Error('Reload the review context before trying another decision.'), {
        code: 'reload_required',
      });
    }
    const loaded = requireContext(unref(contextRef));
    requireCapability(loaded, action);
    return loaded;
  }

  async function mutate(action, toState, rationale, loaded, conditional = {}) {
    pendingAction.value = action;
    submitting.value = true;
    error.value = null;
    try {
      const response = await transitionPhenopacket(
        loaded.phenopacket_id,
        toState,
        rationale,
        loaded.record_revision,
        conditional
      );
      const nextContext = await reload();
      await onCompleted?.({ action, result: response.data, context: nextContext });
      return response.data;
    } catch (mutationError) {
      const mappedConflict = conflictDetail(mutationError);
      if (mappedConflict) conflict.value = mappedConflict;
      else error.value = mutationError;
      window.logService?.error?.('Review decision failed', {
        routeId: unref(id),
        loadedRecordId: loaded.phenopacket_id,
        action,
        error: mutationError?.message,
      });
      throw mutationError;
    } finally {
      pendingAction.value = null;
      submitting.value = false;
    }
  }

  async function approve({ rationale, independentReview, noUnmanagedConflict }) {
    const loaded = assertReady('approve');
    const issueCount = loaded.discussion_summary?.open_blocking_issues;
    if (!Number.isInteger(issueCount) || issueCount < 0) {
      throw new Error('Blocking issue status is unavailable. Reload the review context.');
    }
    if (issueCount > 0) {
      const label = issueCount === 1 ? 'issue remains' : 'issues remain';
      throw new Error(`${issueCount} unresolved blocking ${label}.`);
    }
    if (independentReview !== true || noUnmanagedConflict !== true) {
      throw new Error('Both approval attestations are required.');
    }
    const candidate = requireSnapshot(loaded.candidate, 'candidate');
    return await mutate('approve', 'approved', requiredRationale(rationale), loaded, {
      candidateRevisionId: candidate.id,
      candidateContentSha256: candidate.digest,
      attestation: { independentReview: true, noUnmanagedConflict: true },
    });
  }

  async function requestChanges({ rationale }) {
    const loaded = assertReady('request_changes');
    return await mutate(
      'request_changes',
      'changes_requested',
      requiredRationale(rationale),
      loaded
    );
  }

  async function reopenApproved({ rationale }) {
    const loaded = assertReady('request_changes');
    return await mutate(
      'reopen_approved',
      'changes_requested',
      requiredRationale(rationale),
      loaded
    );
  }

  async function publish({ rationale }) {
    const loaded = assertReady('publish');
    const approved = requireSnapshot(loaded.approved, 'approval');
    return await mutate('publish', 'published', requiredRationale(rationale), loaded, {
      approvedRevisionId: approved.id,
      approvedContentSha256: approved.digest,
    });
  }

  async function withdraw({ rationale }) {
    const loaded = assertReady('withdraw');
    return await mutate('withdraw', 'draft', requiredRationale(rationale), loaded);
  }

  return {
    pendingAction,
    submitting,
    error,
    conflict,
    approve,
    requestChanges,
    reopenApproved,
    publish,
    withdraw,
  };
}
