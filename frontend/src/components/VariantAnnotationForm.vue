<template>
  <v-card variant="outlined" class="variant-annotation-section">
    <v-card-title class="d-flex align-center bg-purple-lighten-5">
      <v-icon left>mdi-dna</v-icon>
      Variant Annotation
      <v-spacer />
      <v-chip v-if="modelValue" color="primary" size="small"> VEP Annotated </v-chip>
    </v-card-title>

    <v-card-text>
      <!-- Variant Input -->
      <v-text-field
        v-model="variantInput"
        label="Variant Notation *"
        hint="Enter variant in HGVS, VCF, or rsID format (e.g., NM_000458.4:c.544+1G>A, 17-36459258-A-G, rs56116432)"
        persistent-hint
        :loading="loading"
        :error-messages="errorMessages"
        clearable
        @update:model-value="handleInputChange"
      >
        <template #append>
          <v-btn
            v-if="variantInput && variantInput.length >= 3"
            color="primary"
            variant="text"
            size="small"
            :loading="loading"
            @click="annotateInput"
          >
            Annotate
          </v-btn>
        </template>
      </v-text-field>

      <!-- Format Detection -->
      <div v-if="detectedFormat" class="mb-4">
        <v-chip size="small" variant="outlined" prepend-icon="mdi-information-outline">
          Detected format: {{ detectedFormat }}
        </v-chip>
      </div>

      <!-- Validation Errors -->
      <v-alert
        v-if="validation && !validation.is_valid"
        type="warning"
        variant="tonal"
        class="mb-4"
      >
        <div class="font-weight-bold">Invalid variant notation</div>
        <ul v-if="validation.errors.length > 0" class="mt-2">
          <li v-for="(err, index) in validation.errors" :key="index">{{ err }}</li>
        </ul>
        <div v-if="validation.suggestions.length > 0" class="mt-2">
          <strong>Suggestions:</strong>
          <ul>
            <li v-for="(sug, index) in validation.suggestions" :key="index">{{ sug }}</li>
          </ul>
        </div>
      </v-alert>

      <!-- VEP Annotation Results -->
      <div v-if="annotation" class="annotation-results">
        <!-- Summary Card -->
        <v-card variant="outlined" class="mb-4">
          <v-card-title class="text-h6">
            Annotation Summary
            <v-chip
              :color="getImpactColor(annotation.impact)"
              size="small"
              variant="flat"
              class="ml-2"
            >
              {{ annotation.impact }}
            </v-chip>
          </v-card-title>
          <v-card-text>
            <v-row dense>
              <v-col cols="12" md="6">
                <div class="text-caption text-medium-emphasis">Gene</div>
                <div class="text-body-1 font-weight-medium">
                  {{ annotation.gene_symbol || 'Unknown' }}
                </div>
              </v-col>
              <v-col cols="12" md="6">
                <div class="text-caption text-medium-emphasis">Consequence</div>
                <div class="text-body-1">
                  {{ formatConsequence(annotation.most_severe_consequence) }}
                </div>
              </v-col>
              <v-col cols="12" md="6">
                <div class="text-caption text-medium-emphasis">Location</div>
                <div class="text-body-1">
                  chr{{ annotation.chromosome }}:{{ annotation.position }} ({{
                    annotation.assembly
                  }})
                </div>
              </v-col>
              <v-col cols="12" md="6">
                <div class="text-caption text-medium-emphasis">Allele</div>
                <div class="text-body-1 font-mono">{{ annotation.allele_string }}</div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- Functional Predictions -->
        <v-card variant="outlined" class="mb-4">
          <v-card-title class="text-subtitle-1">Functional Predictions</v-card-title>
          <v-card-text>
            <v-row dense>
              <!-- CADD Score -->
              <v-col cols="12" md="6">
                <div class="text-caption text-medium-emphasis">CADD Phred Score</div>
                <div class="d-flex align-center">
                  <v-progress-linear
                    :model-value="annotation.cadd_score || 0"
                    :color="getCaddColor(annotation.cadd_score)"
                    max="50"
                    height="20"
                    class="mr-2"
                  >
                    <template #default>
                      <strong>{{ annotation.cadd_score?.toFixed(1) || 'N/A' }}</strong>
                    </template>
                  </v-progress-linear>
                  <v-tooltip location="top">
                    <template #activator="{ props: tooltipProps }">
                      <v-icon v-bind="tooltipProps" size="small" color="grey">
                        mdi-information-outline
                      </v-icon>
                    </template>
                    <div>
                      CADD score &gt; 30 suggests likely pathogenic<br />
                      CADD score &gt; 20 suggests possibly pathogenic
                    </div>
                  </v-tooltip>
                </div>
              </v-col>

              <!-- gnomAD Frequency -->
              <v-col cols="12" md="6">
                <div class="text-caption text-medium-emphasis">gnomAD Allele Frequency</div>
                <div class="d-flex align-center">
                  <span class="text-body-1 font-mono">
                    {{ formatFrequency(annotation.gnomad_af) }}
                  </span>
                  <v-chip
                    v-if="annotation.gnomad_af !== null"
                    :color="getFrequencyColor(annotation.gnomad_af)"
                    size="x-small"
                    variant="flat"
                    class="ml-2"
                  >
                    {{ getFrequencyLabel(annotation.gnomad_af) }}
                  </v-chip>
                </div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- HGVS Notations -->
        <v-card variant="outlined" class="mb-4">
          <v-card-title class="text-subtitle-1">HGVS Notations</v-card-title>
          <v-card-text>
            <v-list density="compact">
              <v-list-item v-if="annotation.hgvsc">
                <template #prepend>
                  <v-icon color="blue">mdi-code-tags</v-icon>
                </template>
                <v-list-item-title>Coding (c.)</v-list-item-title>
                <v-list-item-subtitle class="font-mono">{{
                  annotation.hgvsc
                }}</v-list-item-subtitle>
              </v-list-item>

              <v-list-item v-if="annotation.hgvsp">
                <template #prepend>
                  <v-icon color="purple">mdi-alpha-p-box</v-icon>
                </template>
                <v-list-item-title>Protein (p.)</v-list-item-title>
                <v-list-item-subtitle class="font-mono">{{
                  annotation.hgvsp
                }}</v-list-item-subtitle>
              </v-list-item>

              <v-list-item v-if="annotation.transcript_id">
                <template #prepend>
                  <v-icon color="green">mdi-file-document</v-icon>
                </template>
                <v-list-item-title>Transcript</v-list-item-title>
                <v-list-item-subtitle class="font-mono">
                  {{ annotation.transcript_id }}
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>

        <!-- Save to Phenopacket Button -->
        <v-btn color="success" prepend-icon="mdi-check" block @click="saveVariant">
          Add Variant to Phenopacket
        </v-btn>
      </div>

      <!-- No Annotation Yet -->
      <v-card v-else variant="outlined" class="text-center pa-8">
        <v-icon size="64" color="grey-lighten-1">mdi-dna</v-icon>
        <div class="text-h6 mt-4">No variant annotated yet</div>
        <div class="text-body-2 text-medium-emphasis">
          Enter a variant notation above and click "Annotate" to get VEP predictions
        </div>
      </v-card>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useVariantAnnotation } from '@/composables/useVariantAnnotation';

const props = defineProps({
  modelValue: {
    type: Object,
    default: null,
  },
});

const emit = defineEmits(['update:modelValue']);

// Composable
const { annotation, validation, loading, error, validateVariant, annotateVariant } =
  useVariantAnnotation();

// Local state
const variantInput = ref('');
const detectedFormat = ref(null);

// Detect format from input
const detectFormat = (input) => {
  if (!input) return null;

  if (input.includes(':c.')) return 'HGVS coding (c.)';
  if (input.includes(':p.')) return 'HGVS protein (p.)';
  if (input.includes(':g.')) return 'HGVS genomic (g.)';
  if (/^(chr)?[\dXY]+-\d+-[ATCG]+-[ATCG]+/.test(input)) return 'VCF format';
  if (/^rs\d+/.test(input)) return 'rsID';
  if (/^[\dXY]+:\d+-\d+:(DEL|DUP|INS|INV)/.test(input)) return 'CNV notation';

  return 'Unknown format';
};

// Handle input change with debouncing
let debounceTimer = null;
const handleInputChange = (value) => {
  detectedFormat.value = detectFormat(value);

  // Clear previous timer
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }

  // Debounce validation
  if (value && value.length >= 5) {
    debounceTimer = setTimeout(async () => {
      try {
        await validateVariant(value);
      } catch {
        // Validation errors are already handled by composable
      }
    }, 500);
  }
};

// Annotate input
const annotateInput = async () => {
  if (!variantInput.value) return;

  try {
    await annotateVariant(variantInput.value);
  } catch {
    // Error already handled by composable
  }
};

// Save variant to phenopacket
const saveVariant = () => {
  if (!annotation.value) return;

  const variantData = {
    vcfAllele: {
      genomeAssembly: annotation.value.assembly,
      chr: annotation.value.chromosome,
      pos: annotation.value.position,
      ref: annotation.value.allele_string?.split('/')[0],
      alt: annotation.value.allele_string?.split('/')[1],
    },
    interpretation: {
      mostSevereConsequence: annotation.value.most_severe_consequence,
      impact: annotation.value.impact,
      caddScore: annotation.value.cadd_score,
      gnomadAf: annotation.value.gnomad_af,
    },
    annotation: {
      hgvsc: annotation.value.hgvsc,
      hgvsp: annotation.value.hgvsp,
      transcriptId: annotation.value.transcript_id,
      geneSymbol: annotation.value.gene_symbol,
    },
  };

  emit('update:modelValue', variantData);

  window.logService.info('Variant added to phenopacket', {
    variant: variantInput.value,
    consequence: annotation.value.most_severe_consequence,
    gene: annotation.value.gene_symbol,
  });
};

// Error messages for input field
const errorMessages = computed(() => {
  if (error.value) return [error.value];
  if (validation.value && !validation.value.is_valid) return validation.value.errors;
  return [];
});

// Helper functions
const getImpactColor = (impact) => {
  const colors = {
    HIGH: 'error',
    MODERATE: 'warning',
    LOW: 'info',
    MODIFIER: 'grey',
  };
  return colors[impact] || 'grey';
};

const getCaddColor = (score) => {
  if (!score) return 'grey';
  if (score >= 30) return 'error';
  if (score >= 20) return 'warning';
  return 'success';
};

const getFrequencyColor = (freq) => {
  if (freq === null || freq === undefined) return 'grey';
  if (freq === 0) return 'error'; // Novel variant
  if (freq < 0.0001) return 'warning'; // Ultra-rare
  if (freq < 0.01) return 'info'; // Rare
  return 'success'; // Common
};

const getFrequencyLabel = (freq) => {
  if (freq === null || freq === undefined) return 'Unknown';
  if (freq === 0) return 'Novel';
  if (freq < 0.0001) return 'Ultra-rare';
  if (freq < 0.01) return 'Rare';
  return 'Common';
};

const formatFrequency = (freq) => {
  if (freq === null || freq === undefined) return 'N/A';
  if (freq === 0) return '0 (Novel)';
  return freq.toExponential(2);
};

const formatConsequence = (consequence) => {
  if (!consequence) return 'Unknown';
  return consequence.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
};

// Watch for prop changes
watch(
  () => props.modelValue,
  (newValue) => {
    if (newValue && newValue.annotation?.hgvsc) {
      variantInput.value = newValue.annotation.hgvsc;
    }
  },
  { immediate: true }
);
</script>

<style scoped>
.variant-annotation-section {
  margin-bottom: 1rem;
}

.annotation-results {
  margin-top: 1rem;
}

.font-mono {
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.9em;
}
</style>
