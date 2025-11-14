/**
 * Composable for VEP variant annotation.
 *
 * Handles variant validation and VEP API calls.
 *
 * @returns {{annotation: Ref, loading: Ref, error: Ref, annotate: Function, reset: Function}}
 *
 * @example
 * const { annotation, loading, annotate } = useVEPAnnotation()
 * await annotate('17-36459258-A-G')
 * // annotation.value = { cadd_score, gnomad_af, consequence, ... }
 */

import { ref } from 'vue';
import axios from 'axios';

export function useVEPAnnotation() {
  const annotation = ref(null);
  const loading = ref(false);
  const error = ref(null);

  const annotate = async (variant) => {
    loading.value = true;
    error.value = null;
    annotation.value = null;

    try {
      const response = await axios.post('/api/v2/variants/annotate', null, {
        params: { variant },
      });

      annotation.value = response.data;

      window.logService.info('VEP annotation completed', {
        variant,
        consequence: annotation.value.most_severe_consequence,
      });

      return annotation.value;
    } catch (e) {
      error.value = e;
      window.logService.error('VEP annotation failed', {
        variant,
        error: e.message,
      });
      throw e;
    } finally {
      loading.value = false;
    }
  };

  const reset = () => {
    annotation.value = null;
    loading.value = false;
    error.value = null;
  };

  return { annotation, loading, error, annotate, reset };
}
