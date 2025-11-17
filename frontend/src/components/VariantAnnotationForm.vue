<template>
  <v-card variant="outlined" class="mb-4">
    <v-card-title class="bg-purple-lighten-5">
      <v-icon left>mdi-dna</v-icon>
      Variant Information
    </v-card-title>

    <v-card-text>
      <!-- List of added variants -->
      <div v-if="variants.length > 0" class="mb-4">
        <v-list density="compact">
          <v-list-item v-for="(variant, index) in variants" :key="index" class="mb-2" border>
            <template #prepend>
              <v-icon color="purple">mdi-dna</v-icon>
            </template>

            <v-list-item-title>
              {{ variant.label }}
            </v-list-item-title>

            <v-list-item-subtitle v-if="variant.geneSymbol">
              Gene: {{ variant.geneSymbol }}
              <span v-if="variant.consequence">
                | {{ variant.consequence }}
                <span v-if="variant.impact">({{ variant.impact }})</span>
              </span>
              <span v-if="variant.caddScore"> | CADD: {{ variant.caddScore }}</span>
            </v-list-item-subtitle>

            <template #append>
              <v-btn
                icon="mdi-delete"
                variant="text"
                size="small"
                color="error"
                @click="removeVariant(index)"
              />
            </template>
          </v-list-item>
        </v-list>
      </div>

      <v-divider v-if="variants.length > 0" class="mb-4" />

      <!-- Add new variant -->
      <div>
        <v-text-field
          v-model="variantInput"
          label="Variant Notation"
          hint="HGVS, VCF, or rsID format (e.g., chr17-37739455-G-A, NM_000458.4:c.544+1G>A)"
          persistent-hint
          :loading="loading"
          :error-messages="error ? [error] : []"
          clearable
          @keyup.enter="annotate"
        >
          <template #append>
            <v-btn
              v-if="variantInput"
              color="primary"
              variant="text"
              size="small"
              :loading="loading"
              @click="annotate"
            >
              Annotate
            </v-btn>
          </template>
        </v-text-field>

        <!-- Annotation result -->
        <div v-if="annotation" class="mt-2">
          <v-alert type="success" variant="tonal">
            <div class="font-weight-bold">{{ annotation.gene_symbol }}</div>
            <div class="text-caption">
              {{ annotation.most_severe_consequence }}
              <span v-if="annotation.impact">({{ annotation.impact }})</span>
            </div>
            <div v-if="annotation.cadd_score" class="text-caption">
              CADD Score: {{ annotation.cadd_score.toFixed(1) }}
            </div>

            <v-btn
              color="success"
              size="small"
              class="mt-2"
              prepend-icon="mdi-plus"
              @click="addAnnotatedVariant"
            >
              Add Variant
            </v-btn>
          </v-alert>
        </div>

        <!-- Add without annotation button -->
        <v-btn
          v-if="variantInput && !annotation && !loading"
          color="primary"
          size="small"
          class="mt-2"
          prepend-icon="mdi-plus"
          @click="addVariantDirect"
        >
          Add Without Annotation
        </v-btn>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useVariantAnnotation } from '@/composables/useVariantAnnotation';

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
  subjectId: {
    type: String,
    default: 'subject-1',
  },
});

const emit = defineEmits(['update:modelValue']);

const { annotation, loading, error, annotateVariant, reset } = useVariantAnnotation();

const variantInput = ref('');

/**
 * Extract simplified variant info from interpretations array
 * For display purposes only
 */
const variants = computed(() => {
  return (props.modelValue || [])
    .map((interp) => {
      const genomicInterps = interp.diagnosis?.genomicInterpretations || [];
      if (genomicInterps.length === 0) return null;

      const variantInterp = genomicInterps[0].variantInterpretation;
      const descriptor = variantInterp?.variationDescriptor;

      if (!descriptor) return null;

      return {
        label: descriptor.label || descriptor.id || 'Unknown variant',
        geneSymbol: descriptor.geneContext?.symbol,
        consequence: descriptor.moleculeContext,
        impact: variantInterp.impact,
        caddScore: variantInterp.caddScore,
      };
    })
    .filter(Boolean);
});

/**
 * Annotate variant using VEP
 */
const annotate = async () => {
  if (!variantInput.value) return;

  reset();

  try {
    await annotateVariant(variantInput.value);
  } catch (err) {
    // Error handled by composable
    window.logService.error('Failed to annotate variant', {
      variant: variantInput.value,
      error: err.message,
    });
  }
};

/**
 * Add variant with VEP annotation
 */
const addAnnotatedVariant = () => {
  if (!annotation.value || !variantInput.value) return;

  const interpretation = createInterpretation(
    variantInput.value,
    annotation.value.gene_symbol || 'HNF1B',
    {
      consequence: annotation.value.most_severe_consequence,
      impact: annotation.value.impact,
      caddScore: annotation.value.cadd_score,
    }
  );

  const updatedInterpretations = [...props.modelValue, interpretation];
  emit('update:modelValue', updatedInterpretations);

  window.logService.info('Variant added to phenopacket', {
    variant: variantInput.value,
    geneSymbol: annotation.value.gene_symbol,
  });

  // Clear form
  variantInput.value = '';
  reset();
};

/**
 * Add variant without annotation (direct entry)
 */
const addVariantDirect = () => {
  if (!variantInput.value) return;

  const interpretation = createInterpretation(variantInput.value, 'HNF1B');

  const updatedInterpretations = [...props.modelValue, interpretation];
  emit('update:modelValue', updatedInterpretations);

  window.logService.info('Variant added to phenopacket (no annotation)', {
    variant: variantInput.value,
  });

  // Clear form
  variantInput.value = '';
  reset();
};

/**
 * Remove variant from list
 */
const removeVariant = (index) => {
  const updatedInterpretations = props.modelValue.filter((_, i) => i !== index);
  emit('update:modelValue', updatedInterpretations);

  window.logService.info('Variant removed from phenopacket', { index });
};

/**
 * Create GA4GH Phenopackets v2 interpretation structure
 * @param {string} variantNotation - Variant notation (HGVS, VCF, etc.)
 * @param {string} geneSymbol - Gene symbol
 * @param {object} annotationData - Optional VEP annotation data
 */
const createInterpretation = (variantNotation, geneSymbol, annotationData = {}) => {
  const interpretationId = `interpretation-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  const variantId = `var:${variantNotation}`;

  const variationDescriptor = {
    id: variantId,
    label: variantNotation,
    geneContext: {
      valueId: geneSymbol === 'HNF1B' ? 'HGNC:5024' : '',
      symbol: geneSymbol,
    },
    moleculeContext: annotationData.consequence || 'genomic',
  };

  // Add variation object with notation
  variationDescriptor.variation = {
    notation: variantNotation,
  };

  const variantInterpretation = {
    variationDescriptor,
  };

  // Add optional annotation data
  if (annotationData.impact) {
    variantInterpretation.impact = annotationData.impact;
  }
  if (annotationData.caddScore) {
    variantInterpretation.caddScore = annotationData.caddScore;
  }

  return {
    id: interpretationId,
    progressStatus: 'IN_PROGRESS',
    diagnosis: {
      genomicInterpretations: [
        {
          subjectOrBiosampleId: props.subjectId,
          interpretationStatus: 'UNKNOWN',
          variantInterpretation,
        },
      ],
    },
  };
};
</script>

<style scoped>
.v-list-item {
  background-color: rgba(0, 0, 0, 0.02);
}
</style>
