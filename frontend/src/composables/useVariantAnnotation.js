import { ref } from 'vue';
import { apiClient } from '@/api';

/**
 * Composable for variant annotation using VEP
 * Provides validation, annotation, and format conversion
 */
export function useVariantAnnotation() {
  const annotation = ref(null);
  const validation = ref(null);
  const loading = ref(false);
  const error = ref(null);

  /**
   * Validate variant notation
   * @param {string} notation - Variant notation (HGVS, VCF, etc.)
   * @param {string} notationType - Optional notation type hint
   */
  const validateVariant = async (notation, notationType = null) => {
    loading.value = true;
    error.value = null;
    validation.value = null;

    try {
      const response = await apiClient.post('/variants/validate', {
        notation,
        notation_type: notationType,
      });

      validation.value = response.data;

      window.logService.info('Variant validated', {
        notation,
        isValid: validation.value.is_valid,
        notationType: validation.value.notation_type,
      });

      return validation.value;
    } catch (err) {
      error.value = err.message || 'Failed to validate variant';
      window.logService.error('Variant validation failed', {
        notation,
        error: err.message,
      });
      throw err;
    } finally {
      loading.value = false;
    }
  };

  /**
   * Annotate variant with VEP
   * @param {string} variant - Variant notation
   */
  const annotateVariant = async (variant) => {
    loading.value = true;
    error.value = null;
    annotation.value = null;

    try {
      const response = await apiClient.post('/variants/annotate', null, {
        params: { variant },
      });

      annotation.value = response.data;

      window.logService.info('Variant annotated with VEP', {
        variant,
        consequence: annotation.value.most_severe_consequence,
        impact: annotation.value.impact,
        geneSymbol: annotation.value.gene_symbol,
      });

      return annotation.value;
    } catch (err) {
      error.value = err.response?.data?.detail || err.message || 'Failed to annotate variant';
      window.logService.error('Variant annotation failed', {
        variant,
        error: err.message,
      });
      throw err;
    } finally {
      loading.value = false;
    }
  };

  /**
   * Recode variant to all formats
   * @param {string} variant - Variant notation
   */
  const recodeVariant = async (variant) => {
    loading.value = true;
    error.value = null;

    try {
      const response = await apiClient.post('/variants/recode', null, {
        params: { variant },
      });

      window.logService.info('Variant recoded', {
        variant,
        hgvsc: response.data.hgvsc,
        hgvsg: response.data.hgvsg,
      });

      return response.data;
    } catch (err) {
      error.value = err.response?.data?.detail || err.message || 'Failed to recode variant';
      window.logService.error('Variant recoding failed', {
        variant,
        error: err.message,
      });
      throw err;
    } finally {
      loading.value = false;
    }
  };

  /**
   * Get variant suggestions for autocomplete
   * @param {string} partial - Partial variant notation
   */
  const getSuggestions = async (partial) => {
    if (!partial || partial.length < 2) {
      return [];
    }

    try {
      const response = await apiClient.get(`/variants/suggest/${encodeURIComponent(partial)}`);
      return response.data.suggestions || [];
    } catch (err) {
      window.logService.warn('Failed to get variant suggestions', {
        partial,
        error: err.message,
      });
      return [];
    }
  };

  /**
   * Reset all state
   */
  const reset = () => {
    annotation.value = null;
    validation.value = null;
    loading.value = false;
    error.value = null;
  };

  return {
    annotation,
    validation,
    loading,
    error,
    validateVariant,
    annotateVariant,
    recodeVariant,
    getSuggestions,
    reset,
  };
}
