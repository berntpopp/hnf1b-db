// frontend/src/composables/usePhenopacketState.js
// Wave 7 / D.1 §9.3 — composable for state machine actions on a single phenopacket.
import { ref, toValue, watch } from 'vue';
import {
  transitionPhenopacket,
  fetchRevisions,
  getPhenopacketAuditHistory,
} from '@/api/domain/phenopackets';

const SIMPLE_TRANSITION_TARGETS = new Set(['in_review', 'draft', 'archived']);

/**
 * Derive the effective state for UI binding.
 * Falls back to pp.state when the response predates D.2 (no effective_state field).
 *
 * @param {Object|null|undefined} pp - A phenopacket meta object (or null).
 * @returns {string|null} The effective state, or pp.state if not present, or null.
 */
export function effectiveStateOf(pp) {
  if (!pp) return null;
  return pp.effective_state ?? pp.state ?? null;
}

/**
 * Composable encapsulating state-machine operations for one phenopacket.
 *
 * @param {string|import('vue').Ref<string>|(() => string)} phenopacketId - Current public identifier.
 * @returns {{ revisions, loading, error, transitionTo, loadRevisions }}
 */
export function usePhenopacketState(phenopacketId) {
  const revisions = ref([]);
  const loading = ref(false);
  const error = ref(null);
  const historyEntries = ref([]);
  const historyTotal = ref(0);
  const historyLoading = ref(false);
  const historyError = ref(null);
  let recordGeneration = 0;

  const currentPhenopacketId = () => String(toValue(phenopacketId) || '');
  const ownsOperation = (generation, id) =>
    generation === recordGeneration && id === currentPhenopacketId();

  watch(
    currentPhenopacketId,
    () => {
      recordGeneration += 1;
      revisions.value = [];
      loading.value = false;
      error.value = null;
      historyEntries.value = [];
      historyTotal.value = 0;
      historyLoading.value = false;
      historyError.value = null;
    },
    { flush: 'sync' }
  );

  /**
   * POST a state transition.
   * @param {string} toState - Target state (e.g. 'in_review').
   * @param {string} reason - Human-readable reason (required by API).
   * @param {number} revision - Current optimistic-lock revision.
   * @returns {Promise<Object>} The API response data ({ phenopacket, revision }).
   */
  const transitionTo = async (toState, reason, revision) => {
    if (!SIMPLE_TRANSITION_TARGETS.has(toState)) {
      const message = `State transition '${toState}' requires the review workspace`;
      error.value = message;
      throw new Error(message);
    }

    const id = currentPhenopacketId();
    const generation = recordGeneration;
    loading.value = true;
    error.value = null;
    try {
      const { data } = await transitionPhenopacket(id, toState, reason, revision);
      if (!ownsOperation(generation, id)) return undefined;
      return data;
    } catch (e) {
      if (!ownsOperation(generation, id)) return undefined;
      error.value = e.response?.data?.detail || e.message;
      throw e;
    } finally {
      if (ownsOperation(generation, id)) loading.value = false;
    }
  };

  /**
   * Load the revision list and populate `revisions`.
   * @param {Object} [opts] - Pagination options forwarded to fetchRevisions.
   */
  const loadRevisions = async (opts) => {
    const id = currentPhenopacketId();
    const generation = recordGeneration;
    loading.value = true;
    try {
      const { data } = await fetchRevisions(id, opts);
      if (!ownsOperation(generation, id)) return;
      revisions.value = data.data;
    } finally {
      if (ownsOperation(generation, id)) loading.value = false;
    }
  };

  const loadHistory = async (opts) => {
    const id = currentPhenopacketId();
    const generation = recordGeneration;
    historyLoading.value = true;
    historyError.value = null;

    try {
      const [{ data: firstRevisionPage }, { data: auditData }] = await Promise.all([
        fetchRevisions(id, opts),
        getPhenopacketAuditHistory(id),
      ]);
      if (!ownsOperation(generation, id)) return;

      const revisionRows = [...(firstRevisionPage.data ?? [])];
      const declaredTotal = Number(firstRevisionPage.meta?.total);
      const total =
        Number.isInteger(declaredTotal) && declaredTotal >= revisionRows.length
          ? declaredTotal
          : revisionRows.length;
      const pageSize =
        Number(firstRevisionPage.meta?.page_size) || opts?.pageSize || revisionRows.length || 50;
      let pageNumber = Number(firstRevisionPage.meta?.page) || opts?.pageNumber || 1;
      let fetchedPages = 1;

      while (revisionRows.length < total) {
        if (fetchedPages >= 100) {
          throw new Error('Revision history exceeds the supported 100-page safety bound.');
        }
        pageNumber += 1;
        const { data: nextPage } = await fetchRevisions(id, { pageSize, pageNumber });
        if (!ownsOperation(generation, id)) return;
        const nextRows = nextPage.data ?? [];
        if (nextRows.length === 0) {
          throw new Error('Revision history pagination ended before the declared total.');
        }
        revisionRows.push(...nextRows);
        fetchedPages += 1;
      }

      const auditByRevisionId = new Map(
        auditData
          .filter((entry) => entry?.source === 'revision' && entry?.id != null)
          .map((entry) => [String(entry.id), entry])
      );

      historyEntries.value = revisionRows.map((revision) => {
        const auditEntry = auditByRevisionId.get(String(revision.id));

        return {
          id: String(revision.id),
          revisionNumber: revision.revision_number,
          state: revision.state ?? revision.to_state ?? auditEntry?.state_transition?.to ?? null,
          actor: revision.actor_username ?? auditEntry?.changed_by ?? null,
          timestamp: revision.created_at ?? auditEntry?.changed_at ?? null,
          summary:
            auditEntry?.change_summary ?? revision.change_reason ?? auditEntry?.change_reason,
        };
      });
      historyTotal.value = total;
    } catch (e) {
      if (!ownsOperation(generation, id)) return;
      historyError.value = e.response?.data?.detail || e.message || 'Failed to load history';
      throw e;
    } finally {
      if (ownsOperation(generation, id)) historyLoading.value = false;
    }
  };

  return {
    revisions,
    loading,
    error,
    historyEntries,
    historyTotal,
    historyLoading,
    historyError,
    transitionTo,
    loadRevisions,
    loadHistory,
  };
}
