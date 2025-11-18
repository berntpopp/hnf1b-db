<template>
  <v-card elevation="2" class="variant-annotator">
    <v-card-title class="text-h6">Variant Annotation Tool</v-card-title>
    <v-card-subtitle>
      Annotate variants using Ensembl Variant Effect Predictor (VEP)
    </v-card-subtitle>

    <v-card-text>
      <!-- Input Section -->
      <v-row>
        <v-col cols="12">
          <v-text-field
            v-model="variantInput"
            label="Variant Notation"
            placeholder="e.g., NM_000458.4:c.544+1G>A or 17-36459258-A-G"
            variant="outlined"
            density="comfortable"
            :error-messages="validationError"
            @blur="validateInput"
            @keyup.enter="handleAnnotate"
          >
            <template #append-inner>
              <v-chip v-if="detectedFormat" size="small" :color="formatColor" variant="flat">
                {{ detectedFormat }}
              </v-chip>
            </template>
          </v-text-field>
        </v-col>
      </v-row>

      <!-- Format Examples -->
      <v-row dense class="mb-2">
        <v-col cols="12">
          <v-chip-group class="format-examples">
            <v-chip
              size="small"
              variant="outlined"
              @click="variantInput = 'NM_000458.4:c.544+1G>A'"
            >
              HGVS Example
            </v-chip>
            <v-chip size="small" variant="outlined" @click="variantInput = '17-36459258-A-G'">
              VCF Example
            </v-chip>
            <v-chip size="small" variant="outlined" @click="variantInput = 'rs56116432'">
              rsID Example
            </v-chip>
          </v-chip-group>
        </v-col>
      </v-row>

      <!-- Annotate Button -->
      <v-row>
        <v-col cols="12">
          <v-btn
            color="primary"
            size="large"
            block
            :loading="loading"
            :disabled="!variantInput || !!validationError"
            @click="handleAnnotate"
          >
            <v-icon left>mdi-dna</v-icon>
            Annotate Variant
          </v-btn>
        </v-col>
      </v-row>

      <!-- Error Alert -->
      <v-row v-if="errorMessage">
        <v-col cols="12">
          <v-alert type="error" variant="tonal" closable @click:close="clearError">
            {{ errorMessage }}
          </v-alert>
        </v-col>
      </v-row>

      <!-- Results Section -->
      <v-row v-if="annotationResult">
        <v-col cols="12">
          <v-card variant="outlined" class="mt-4">
            <v-card-title class="text-subtitle-1">
              Annotation Results
              <v-chip size="small" class="ml-2" color="success" variant="flat">
                {{ annotationResult.input }}
              </v-chip>
            </v-card-title>

            <v-divider />

            <v-card-text>
              <!-- Variant Identity -->
              <v-row dense>
                <v-col cols="12" sm="6">
                  <div class="text-caption text-grey-darken-1">Variant ID</div>
                  <div class="text-body-2 font-weight-medium">
                    {{ annotationResult.id || 'N/A' }}
                  </div>
                </v-col>
                <v-col cols="12" sm="6">
                  <div class="text-caption text-grey-darken-1">Alleles</div>
                  <div class="text-body-2 font-weight-medium">
                    {{ annotationResult.allele_string || 'N/A' }}
                  </div>
                </v-col>
              </v-row>

              <v-divider class="my-3" />

              <!-- Consequence and Impact -->
              <v-row dense>
                <v-col cols="12" sm="6">
                  <div class="text-caption text-grey-darken-1">Most Severe Consequence</div>
                  <div class="text-body-2 font-weight-medium">
                    {{ formatConsequence(annotationResult.most_severe_consequence) }}
                  </div>
                </v-col>
                <v-col cols="12" sm="6">
                  <div class="text-caption text-grey-darken-1">Impact</div>
                  <v-chip
                    :color="getImpactColor(annotationResult.impact)"
                    variant="flat"
                    size="small"
                  >
                    {{ annotationResult.impact || 'UNKNOWN' }}
                  </v-chip>
                </v-col>
              </v-row>

              <!-- CADD Score -->
              <v-row v-if="annotationResult.cadd" dense class="mt-3">
                <v-col cols="12" sm="6">
                  <div class="text-caption text-grey-darken-1">CADD Score (PHRED)</div>
                  <div class="text-body-2 font-weight-medium">
                    {{ formatCADD(annotationResult.cadd.PHRED) }}
                    <v-chip
                      v-if="annotationResult.cadd.PHRED >= 30"
                      size="x-small"
                      color="error"
                      class="ml-2"
                    >
                      Likely Pathogenic
                    </v-chip>
                    <v-chip
                      v-else-if="annotationResult.cadd.PHRED >= 20"
                      size="x-small"
                      color="warning"
                      class="ml-2"
                    >
                      Possibly Pathogenic
                    </v-chip>
                  </div>
                </v-col>
                <v-col cols="12" sm="6">
                  <div class="text-caption text-grey-darken-1">CADD Raw Score</div>
                  <div class="text-body-2 font-weight-medium">
                    {{ formatNumber(annotationResult.cadd.RAW) }}
                  </div>
                </v-col>
              </v-row>

              <!-- gnomAD Frequency -->
              <v-row v-if="annotationResult.gnomad" dense class="mt-3">
                <v-col cols="12" sm="6">
                  <div class="text-caption text-grey-darken-1">gnomAD Allele Frequency</div>
                  <div class="text-body-2 font-weight-medium">
                    {{ formatFrequency(annotationResult.gnomad.af) }}
                  </div>
                </v-col>
                <v-col cols="12" sm="6">
                  <div class="text-caption text-grey-darken-1">gnomAD Allele Count</div>
                  <div class="text-body-2 font-weight-medium">
                    {{ annotationResult.gnomad.ac || 'N/A' }}
                  </div>
                </v-col>
              </v-row>

              <v-divider class="my-3" />

              <!-- Format Conversions -->
              <div class="text-caption text-grey-darken-1 mb-2">Alternative Notations</div>
              <v-chip-group column>
                <v-chip
                  v-for="notation in formatConversions"
                  :key="notation.label"
                  size="small"
                  variant="outlined"
                  @click="copyToClipboard(notation.value)"
                >
                  <strong>{{ notation.label }}:</strong>
                  <span class="ml-1">{{ notation.value }}</span>
                  <v-icon size="small" class="ml-1">mdi-content-copy</v-icon>
                </v-chip>
              </v-chip-group>

              <!-- Transcript Consequences -->
              <v-expansion-panels v-if="transcriptConsequences.length > 0" class="mt-4">
                <v-expansion-panel>
                  <v-expansion-panel-title>
                    <v-icon class="mr-2">mdi-file-document-outline</v-icon>
                    Transcript Consequences ({{ transcriptConsequences.length }})
                  </v-expansion-panel-title>
                  <v-expansion-panel-text>
                    <v-list dense>
                      <v-list-item
                        v-for="(tc, index) in transcriptConsequences"
                        :key="index"
                        class="transcript-item"
                      >
                        <v-list-item-title>
                          {{ tc.transcript_id }}
                          <v-chip v-if="tc.canonical" size="x-small" color="primary" class="ml-2">
                            Canonical
                          </v-chip>
                        </v-list-item-title>
                        <v-list-item-subtitle>
                          {{ tc.consequence_terms?.join(', ') }}
                          <span v-if="tc.hgvsc" class="ml-2">| {{ tc.hgvsc }}</span>
                          <span v-if="tc.hgvsp" class="ml-2">| {{ tc.hgvsp }}</span>
                        </v-list-item-subtitle>
                      </v-list-item>
                    </v-list>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
            </v-card-text>

            <!-- Clear Results Button -->
            <v-card-actions>
              <v-spacer />
              <v-btn variant="text" @click="clearResults">Clear Results</v-btn>
            </v-card-actions>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script>
import { annotateVariant } from '@/api';

export default {
  name: 'VariantAnnotator',

  emits: ['annotated', 'error'],

  data() {
    return {
      variantInput: '',
      validationError: '',
      errorMessage: '',
      loading: false,
      annotationResult: null,
    };
  },

  computed: {
    /**
     * Detect the format of the input variant notation
     */
    detectedFormat() {
      if (!this.variantInput) return null;

      const input = this.variantInput.trim();

      // HGVS format (e.g., NM_000458.4:c.544+1G>A, NC_000017.11:g.36459258A>G)
      if (/^[A-Z]{2}_\d+\.\d+:[cgp]\./.test(input)) {
        return 'HGVS';
      }

      // VCF format (e.g., 17-36459258-A-G, chr17-36459258-A-G)
      if (/^(chr)?\d{1,2}-\d+-[ACGT]+-[ACGT]+$/i.test(input)) {
        return 'VCF';
      }

      // rsID format (e.g., rs56116432)
      if (/^rs\d+$/i.test(input)) {
        return 'rsID';
      }

      return 'Unknown';
    },

    /**
     * Color for format chip based on detected format
     */
    formatColor() {
      if (this.detectedFormat === 'HGVS') return 'primary';
      if (this.detectedFormat === 'VCF') return 'success';
      if (this.detectedFormat === 'rsID') return 'info';
      return 'grey';
    },

    /**
     * Extract transcript consequences from annotation result
     */
    transcriptConsequences() {
      return this.annotationResult?.transcript_consequences || [];
    },

    /**
     * Generate format conversions for display
     */
    formatConversions() {
      if (!this.annotationResult) return [];

      const conversions = [];
      const tc = this.transcriptConsequences[0]; // Use first/canonical transcript

      // VCF format
      if (this.annotationResult.id) {
        conversions.push({
          label: 'VCF',
          value: this.annotationResult.id,
        });
      }

      // HGVS coding
      if (tc?.hgvsc) {
        conversions.push({
          label: 'HGVS (c.)',
          value: tc.hgvsc,
        });
      }

      // HGVS protein
      if (tc?.hgvsp) {
        conversions.push({
          label: 'HGVS (p.)',
          value: tc.hgvsp,
        });
      }

      // rsID
      const rsids = this.annotationResult.colocated_variants?.filter((v) => v.id?.startsWith('rs'));
      if (rsids?.length > 0) {
        conversions.push({
          label: 'rsID',
          value: rsids[0].id,
        });
      }

      return conversions;
    },
  },

  methods: {
    /**
     * Validate input format when user leaves the field
     */
    validateInput() {
      if (!this.variantInput.trim()) {
        this.validationError = '';
        return;
      }

      if (this.detectedFormat === 'Unknown') {
        this.validationError =
          'Invalid format. Use HGVS (NM_000458.4:c.544+1G>A), VCF (17-36459258-A-G), or rsID (rs56116432)';
      } else {
        this.validationError = '';
      }
    },

    /**
     * Handle annotation button click
     */
    async handleAnnotate() {
      // Validate first
      this.validateInput();
      if (this.validationError || !this.variantInput) {
        return;
      }

      this.loading = true;
      this.errorMessage = '';
      this.annotationResult = null;

      try {
        window.logService.info('Annotating variant', { variant: this.variantInput });

        const response = await annotateVariant(this.variantInput.trim());
        this.annotationResult = response.data;

        window.logService.info('Variant annotation successful', {
          consequence: this.annotationResult.most_severe_consequence,
        });

        // Emit event for parent component
        this.$emit('annotated', this.annotationResult);
      } catch (error) {
        window.logService.error('Variant annotation failed', { error: error.message });

        if (error.response?.status === 404) {
          this.errorMessage = 'Variant not found. Please check your notation and try again.';
        } else if (error.response?.status === 400) {
          this.errorMessage =
            error.response.data?.detail || 'Invalid variant notation. Please check the format.';
        } else if (error.response?.status === 503) {
          this.errorMessage = 'VEP service is temporarily unavailable. Please try again later.';
        } else {
          this.errorMessage =
            'An error occurred while annotating the variant. Please try again later.';
        }

        // Emit error event
        this.$emit('error', error);
      } finally {
        this.loading = false;
      }
    },

    /**
     * Clear results and reset form
     */
    clearResults() {
      this.annotationResult = null;
      this.errorMessage = '';
      this.validationError = '';
    },

    /**
     * Clear error message
     */
    clearError() {
      this.errorMessage = '';
    },

    /**
     * Get color for impact severity badge
     */
    getImpactColor(impact) {
      const colorMap = {
        HIGH: 'error',
        MODERATE: 'warning',
        LOW: 'info',
        MODIFIER: 'grey',
      };
      return colorMap[impact] || 'grey';
    },

    /**
     * Format consequence term for display (replace underscores)
     */
    formatConsequence(consequence) {
      if (!consequence) return 'N/A';
      return consequence.replace(/_/g, ' ');
    },

    /**
     * Format CADD score with interpretation
     */
    formatCADD(score) {
      if (score === null || score === undefined) return 'N/A';
      return parseFloat(score).toFixed(2);
    },

    /**
     * Format allele frequency
     */
    formatFrequency(freq) {
      if (freq === null || freq === undefined) return 'N/A';
      if (freq === 0) return '0';
      if (freq < 0.0001) return freq.toExponential(2);
      return freq.toFixed(6);
    },

    /**
     * Format generic numbers
     */
    formatNumber(num) {
      if (num === null || num === undefined) return 'N/A';
      return parseFloat(num).toFixed(4);
    },

    /**
     * Copy text to clipboard
     */
    async copyToClipboard(text) {
      try {
        await navigator.clipboard.writeText(text);
        window.logService.debug('Copied to clipboard', { text });
      } catch (error) {
        window.logService.error('Failed to copy to clipboard', { error: error.message });
      }
    },
  },
};
</script>

<style scoped>
.variant-annotator {
  max-width: 900px;
  margin: 0 auto;
}

.format-examples {
  margin-top: -8px;
}

.transcript-item {
  border-bottom: 1px solid #e0e0e0;
}

.transcript-item:last-child {
  border-bottom: none;
}
</style>
