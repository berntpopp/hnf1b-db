import { ref } from 'vue';
import api from '@/api';

/**
 * Composable for fetching HPO terms grouped by organ system
 * Used for system-grouped phenotype selection UI
 */
export function useGroupedHPO() {
  const groups = ref({});
  const totalTerms = ref(0);
  const totalGroups = ref(0);
  const loading = ref(false);
  const error = ref(null);

  /**
   * Fetch HPO terms grouped by organ system
   * @param {string} recommendation - Optional filter: 'required' or 'recommended'
   */
  const fetchGrouped = async (recommendation = null) => {
    loading.value = true;
    error.value = null;

    try {
      const params = {};
      if (recommendation) {
        params.recommendation = recommendation;
      }

      const response = await api.get('/ontology/hpo/grouped', { params });

      groups.value = response.data.data.groups || {};
      totalTerms.value = response.data.data.total_terms || 0;
      totalGroups.value = response.data.data.total_groups || 0;

      window.logService.info('Loaded grouped HPO terms', {
        totalTerms: totalTerms.value,
        totalGroups: totalGroups.value,
        recommendation,
      });
    } catch (err) {
      error.value = err.message || 'Failed to load grouped HPO terms';
      window.logService.error('Failed to load grouped HPO terms', {
        error: err.message,
        recommendation,
      });
      throw err;
    } finally {
      loading.value = false;
    }
  };

  return {
    groups,
    totalTerms,
    totalGroups,
    loading,
    error,
    fetchGrouped,
  };
}
