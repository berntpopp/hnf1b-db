// frontend/src/composables/usePhenopacketState.js
// Wave 7 / D.1 §9.3 — composable for state machine actions on a single phenopacket.
import { ref } from 'vue';
import { transitionPhenopacket, fetchRevisions } from '@/api/domain/phenopackets';

/**
 * Composable encapsulating state-machine operations for one phenopacket.
 *
 * @param {string} phenopacketId - The phenopacket's public identifier.
 * @returns {{ revisions, loading, error, transitionTo, loadRevisions }}
 */
export function usePhenopacketState(phenopacketId) {
  const revisions = ref([]);
  const loading = ref(false);
  const error = ref(null);

  /**
   * POST a state transition.
   * @param {string} toState - Target state (e.g. 'in_review').
   * @param {string} reason - Human-readable reason (required by API).
   * @param {number} revision - Current optimistic-lock revision.
   * @returns {Promise<Object>} The API response data ({ phenopacket, revision }).
   */
  const transitionTo = async (toState, reason, revision) => {
    loading.value = true;
    error.value = null;
    try {
      const { data } = await transitionPhenopacket(phenopacketId, toState, reason, revision);
      return data;
    } catch (e) {
      error.value = e.response?.data?.detail || e.message;
      throw e;
    } finally {
      loading.value = false;
    }
  };

  /**
   * Load the revision list and populate `revisions`.
   * @param {Object} [opts] - Pagination options forwarded to fetchRevisions.
   */
  const loadRevisions = async (opts) => {
    loading.value = true;
    try {
      const { data } = await fetchRevisions(phenopacketId, opts);
      revisions.value = data.data;
    } finally {
      loading.value = false;
    }
  };

  return { revisions, loading, error, transitionTo, loadRevisions };
}
