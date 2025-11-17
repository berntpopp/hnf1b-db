/**
 * Composable for HPO term autocomplete.
 *
 * Handles API calls, debouncing, and result formatting.
 *
 * @returns {{terms: Ref, loading: Ref, error: Ref, search: Function}}
 *
 * @example
 * const { terms, loading, search } = useHPOAutocomplete()
 * search('renal')
 * // terms.value = [{ id: 'HP:0000107', label: 'Renal cyst', ... }]
 */

import { ref } from 'vue';
import { debounce } from 'lodash-es';
import apiClient from '@/api';

export function useHPOAutocomplete() {
  const terms = ref([]);
  const loading = ref(false);
  const error = ref(null);

  const search = debounce(async (query) => {
    if (!query || query.length < 2) {
      terms.value = [];
      return;
    }

    loading.value = true;
    error.value = null;

    try {
      const response = await apiClient.get('/ontology/hpo/autocomplete', {
        params: { q: query, limit: 20 },
      });

      // Backend returns { data: [...] }, axios wraps in response.data
      // So actual terms are at response.data.data
      const apiTerms = response.data.data || [];

      terms.value = apiTerms.map((term) => ({
        id: term.hpo_id, // Backend returns 'hpo_id', not 'id'
        label: term.label,
        title: `${term.label} (${term.hpo_id})`,
        value: term.hpo_id,
        // Enriched metadata from curated phenotypes table
        category: term.category,
        description: term.description,
        synonyms: term.synonyms,
        recommendation: term.recommendation, // 'required' or 'recommended'
        group: term.group, // Kidney, Hormones, Brain, etc.
        phenopacketCount: term.phenopacket_count,
        similarityScore: term.similarity_score,
      }));

      window.logService.debug('HPO search completed', {
        query,
        results: terms.value.length,
      });
    } catch (e) {
      error.value = e;
      window.logService.error('HPO search failed', {
        query,
        error: e.message,
      });
    } finally {
      loading.value = false;
    }
  }, 300);

  return { terms, loading, error, search };
}
