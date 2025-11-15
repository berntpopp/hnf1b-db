<template>
  <v-card variant="outlined" class="mb-4">
    <v-card-title class="bg-purple-lighten-5">
      <v-icon left>mdi-dna</v-icon>
      Variant Information
    </v-card-title>

    <v-card-text>
      <v-text-field
        v-model="variantInput"
        label="Variant Notation"
        hint="HGVS, VCF, or rsID format (e.g., NM_000458.4:c.544+1G>A)"
        persistent-hint
        :loading="loading"
        :error-messages="error ? [error] : []"
        clearable
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

      <div v-if="annotation" class="mt-4">
        <v-alert type="success" variant="tonal">
          <div class="font-weight-bold">{{ annotation.gene_symbol }}</div>
          <div class="text-caption">
            {{ annotation.most_severe_consequence }} ({{ annotation.impact }})
          </div>
          <div v-if="annotation.cadd_score" class="text-caption">
            CADD: {{ annotation.cadd_score.toFixed(1) }}
          </div>
        </v-alert>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref } from 'vue';
import { useVariantAnnotation } from '@/composables/useVariantAnnotation';

defineProps({
  modelValue: {
    type: Object,
    default: null,
  },
});

const { annotation, loading, error, annotateVariant } = useVariantAnnotation();

const variantInput = ref('');

const annotate = async () => {
  if (!variantInput.value) return;
  try {
    await annotateVariant(variantInput.value);
  } catch {
    // Error handled by composable
  }
};
</script>
