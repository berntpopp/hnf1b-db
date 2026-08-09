import { ref } from 'vue';
import { apiClient } from '@/api';

/**
 * Composable for fetching the laterality-modifier policy (curation console
 * design spec §3.4; plan Task 7): which HPO phenotype terms admit which
 * laterality modifiers (Unilateral / Left / Right / Bilateral).
 *
 * `GET /ontology/laterality-policy` returns
 * `{"data": [{"hpo_id": "HP:0000122", "allowed_modifiers": ["HP:0012833", ...]}, ...]}`
 * -- only terms that admit at least one modifier appear at all. This is the
 * single source of truth for WHICH term admits WHICH modifiers; that must
 * never be hardcoded or special-cased per-term in consuming components.
 * Some terms admit fewer than the full set of four possible modifiers (e.g.
 * HP:0000122 admits Unilateral/Left/Right but not Bilateral) -- consumers
 * must render exactly what this fetch returns, nothing assumed.
 */
export function useLateralityPolicy() {
  // Plain object keyed by hpo_id -> array of allowed modifier HPO ids.
  const policy = ref({});
  const loading = ref(false);
  const error = ref(null);

  const fetchPolicy = async () => {
    loading.value = true;
    error.value = null;

    try {
      const response = await apiClient.get('/ontology/laterality-policy');
      const rows = response.data.data || [];
      const map = {};
      rows.forEach((row) => {
        map[row.hpo_id] = row.allowed_modifiers || [];
      });
      policy.value = map;

      window.logService.info('Loaded laterality policy', {
        termCount: rows.length,
      });
    } catch (err) {
      error.value = err.message || 'Failed to load laterality policy';
      window.logService.error('Failed to load laterality policy', {
        error: err.message,
      });
      throw err;
    } finally {
      loading.value = false;
    }
  };

  return {
    policy,
    loading,
    error,
    fetchPolicy,
  };
}
