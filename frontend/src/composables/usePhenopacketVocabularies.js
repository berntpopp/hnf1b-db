/**
 * Composable for fetching phenopacket controlled vocabularies from API.
 *
 * Provides API-driven dropdown values to ensure frontend never hardcodes
 * backend functionality (per user requirement).
 *
 * All values are fetched from database via API endpoints, following
 * GA4GH Phenopackets v2 standard.
 *
 * @returns {{
 *   sex: Ref<Array>,
 *   interpretationStatus: Ref<Array>,
 *   progressStatus: Ref<Array>,
 *   moleculeContext: Ref<Array>,
 *   allelicState: Ref<Array>,
 *   evidenceCode: Ref<Array>,
 *   loading: Ref<boolean>,
 *   error: Ref<Error|null>,
 *   loadAll: Function
 * }}
 *
 * @example
 * const {
 *   sex,
 *   interpretationStatus,
 *   progressStatus,
 *   loading,
 *   loadAll
 * } = usePhenopacketVocabularies()
 *
 * // Load all vocabularies on component mount
 * onMounted(async () => {
 *   await loadAll()
 * })
 *
 * // Use in form
 * <v-select v-model="phenopacket.subject.sex" :items="sex" item-title="label" item-value="value" />
 */

import { ref } from 'vue';
import apiClient from '@/api';

export function usePhenopacketVocabularies() {
  // Vocabulary data refs
  const sex = ref([]);
  const interpretationStatus = ref([]);
  const progressStatus = ref([]);
  const moleculeContext = ref([]);
  const allelicState = ref([]);
  const evidenceCode = ref([]);

  // State refs
  const loading = ref(false);
  const error = ref(null);

  /**
   * Load a single vocabulary from API
   */
  const loadVocabulary = async (endpoint, targetRef) => {
    try {
      const response = await apiClient.get(`/ontology/vocabularies/${endpoint}`);
      targetRef.value = response.data.data || [];

      window.logService.debug(`Loaded vocabulary: ${endpoint}`, {
        count: targetRef.value.length,
      });
    } catch (e) {
      window.logService.error(`Failed to load vocabulary: ${endpoint}`, {
        error: e.message,
      });
      throw e;
    }
  };

  /**
   * Load all controlled vocabularies from API
   */
  const loadAll = async () => {
    loading.value = true;
    error.value = null;

    try {
      await Promise.all([
        loadVocabulary('sex', sex),
        loadVocabulary('interpretation-status', interpretationStatus),
        loadVocabulary('progress-status', progressStatus),
        loadVocabulary('molecule-context', moleculeContext),
        loadVocabulary('allelic-state', allelicState),
        loadVocabulary('evidence-code', evidenceCode),
      ]);

      window.logService.info('All phenopacket vocabularies loaded', {
        vocabularies: {
          sex: sex.value.length,
          interpretationStatus: interpretationStatus.value.length,
          progressStatus: progressStatus.value.length,
          moleculeContext: moleculeContext.value.length,
          allelicState: allelicState.value.length,
          evidenceCode: evidenceCode.value.length,
        },
      });
    } catch (e) {
      error.value = e;
      window.logService.error('Failed to load phenopacket vocabularies', {
        error: e.message,
      });
      throw e;
    } finally {
      loading.value = false;
    }
  };

  return {
    // Vocabulary data
    sex,
    interpretationStatus,
    progressStatus,
    moleculeContext,
    allelicState,
    evidenceCode,

    // State
    loading,
    error,

    // Actions
    loadAll,
  };
}
