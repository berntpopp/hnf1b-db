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
 *   allelicState: Ref<Array>,
 *   evidenceCode: Ref<Array>,
 *   cohort: Ref<Array>,
 *   detectionMethod: Ref<Array>,
 *   segregation: Ref<Array>,
 *   familyHistory: Ref<Array>,
 *   publicationType: Ref<Array>,
 *   classificationSystem: Ref<Array>,
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
import { apiClient } from '@/api';

export function usePhenopacketVocabularies() {
  // Vocabulary data refs
  const sex = ref([]);
  const interpretationStatus = ref([]);
  const progressStatus = ref([]);
  const allelicState = ref([]);
  const evidenceCode = ref([]);

  // Curation vocabularies (spec §4.6). Added explicitly rather than by making
  // this composable generic: the five pre-existing endpoints have four different
  // item shapes, so a generic loader would have to special-case them anyway.
  const cohort = ref([]);
  const detectionMethod = ref([]);
  const segregation = ref([]);
  const familyHistory = ref([]);

  // Phase 3 curation console vocabularies (curation console spec §4).
  const publicationType = ref([]);
  const classificationSystem = ref([]);

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
        loadVocabulary('allelic-state', allelicState),
        loadVocabulary('evidence-code', evidenceCode),
        loadVocabulary('cohort', cohort),
        loadVocabulary('detection-method', detectionMethod),
        loadVocabulary('segregation', segregation),
        loadVocabulary('family-history', familyHistory),
        loadVocabulary('publication-type', publicationType),
        loadVocabulary('classification-system', classificationSystem),
      ]);

      window.logService.info('All phenopacket vocabularies loaded', {
        vocabularies: {
          sex: sex.value.length,
          interpretationStatus: interpretationStatus.value.length,
          progressStatus: progressStatus.value.length,
          allelicState: allelicState.value.length,
          evidenceCode: evidenceCode.value.length,
          cohort: cohort.value.length,
          detectionMethod: detectionMethod.value.length,
          segregation: segregation.value.length,
          familyHistory: familyHistory.value.length,
          publicationType: publicationType.value.length,
          classificationSystem: classificationSystem.value.length,
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
    allelicState,
    evidenceCode,
    cohort,
    detectionMethod,
    segregation,
    familyHistory,
    publicationType,
    classificationSystem,

    // State
    loading,
    error,

    // Actions
    loadAll,
  };
}
