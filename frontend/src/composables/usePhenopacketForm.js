/**
 * Composable for phenopacket form state and submission.
 *
 * Centralizes form logic and API interaction.
 *
 * @param {Object|null} initialData - Existing phenopacket for editing (null for create)
 * @returns {{phenopacket: Ref, loading: Ref, error: Ref, isEditing: ComputedRef, submit: Function, reset: Function}}
 *
 * @example
 * // Create mode
 * const { phenopacket, submit } = usePhenopacketForm()
 *
 * // Edit mode
 * const { phenopacket, submit, isEditing } = usePhenopacketForm(existingPhenopacket)
 */

import { ref, computed } from 'vue';
import { createPhenopacket, updatePhenopacket } from '@/api';
import { useRouter } from 'vue-router';

export function usePhenopacketForm(initialData = null) {
  const router = useRouter();

  const phenopacket = ref(
    initialData || {
      id: `phenopacket-${Date.now()}`,
      subject: {
        id: '',
        sex: 'UNKNOWN_SEX',
      },
      phenotypicFeatures: [],
      interpretations: [],
      metaData: {
        created: new Date().toISOString(),
        createdBy: 'HNF1B-DB Curation Interface',
        resources: [
          {
            id: 'hp',
            name: 'human phenotype ontology',
            url: 'http://purl.obolibrary.org/obo/hp.owl',
            version: '2024-01-16',
            namespacePrefix: 'HP',
            iriPrefix: 'http://purl.obolibrary.org/obo/HP_',
          },
        ],
      },
    }
  );

  const loading = ref(false);
  const error = ref(null);
  const isEditing = computed(() => !!initialData);

  const submit = async () => {
    loading.value = true;
    error.value = null;

    try {
      const apiCall = isEditing.value ? updatePhenopacket : createPhenopacket;
      const result = await apiCall(phenopacket.value.id, phenopacket.value);

      window.logService.info('Phenopacket saved', {
        id: phenopacket.value.id,
        mode: isEditing.value ? 'update' : 'create',
      });

      // Navigate to detail page
      router.push(`/phenopackets/${result.id}`);

      return result;
    } catch (e) {
      error.value = e;
      window.logService.error('Phenopacket save failed', {
        id: phenopacket.value.id,
        error: e.message,
      });
      throw e;
    } finally {
      loading.value = false;
    }
  };

  const reset = () => {
    phenopacket.value = {
      id: `phenopacket-${Date.now()}`,
      subject: {
        id: '',
        sex: 'UNKNOWN_SEX',
      },
      phenotypicFeatures: [],
      interpretations: [],
      metaData: {
        created: new Date().toISOString(),
        createdBy: 'HNF1B-DB Curation Interface',
      },
    };
    error.value = null;
  };

  return { phenopacket, loading, error, isEditing, submit, reset };
}
