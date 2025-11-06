<!-- src/components/phenopacket/InterpretationsCard.vue -->
<template>
  <v-card outlined>
    <v-card-title class="text-subtitle-1 py-2 bg-purple-lighten-5">
      <v-icon left color="deep-purple" size="small"> mdi-dna </v-icon>
      Genomic Interpretations ({{ uniqueInterpretations.length }})
    </v-card-title>
    <v-card-text class="pa-2">
      <v-alert v-if="uniqueInterpretations.length === 0" type="info" density="compact">
        No genomic interpretations recorded
      </v-alert>

      <v-expansion-panels v-else accordion>
        <v-expansion-panel v-for="(interpretation, index) in uniqueInterpretations" :key="index">
          <v-expansion-panel-title>
            <v-icon left color="deep-purple" size="small"> mdi-dna </v-icon>
            <span class="font-weight-medium">
              {{ getVariantSummary(interpretation) || `Variant ${index + 1}` }}
            </span>
          </v-expansion-panel-title>

          <v-expansion-panel-text>
            <v-list v-if="interpretation.diagnosis" density="compact">
              <div
                v-for="(gi, giIndex) in interpretation.diagnosis.genomicInterpretations"
                :key="giIndex"
                class="mb-3"
              >
                <div v-if="gi.variantInterpretation">
                  <div v-if="gi.variantInterpretation.variationDescriptor">
                    <v-list-item class="px-0">
                      <v-list-item-title class="font-weight-bold">
                        Variant Label
                      </v-list-item-title>
                      <v-list-item-subtitle>
                        {{ gi.variantInterpretation.variationDescriptor.label || 'N/A' }}
                      </v-list-item-subtitle>
                    </v-list-item>

                    <v-list-item
                      v-if="gi.variantInterpretation.variationDescriptor.geneContext"
                      class="px-0"
                    >
                      <v-list-item-title class="font-weight-bold"> Gene </v-list-item-title>
                      <v-list-item-subtitle>
                        <v-chip color="blue" size="small" class="mr-1">
                          {{ gi.variantInterpretation.variationDescriptor.geneContext.valueId }}
                        </v-chip>
                        {{ gi.variantInterpretation.variationDescriptor.geneContext.symbol }}
                      </v-list-item-subtitle>
                    </v-list-item>

                    <v-list-item class="px-0">
                      <v-list-item-title class="font-weight-bold">
                        Classification
                      </v-list-item-title>
                      <v-list-item-subtitle>
                        <v-chip
                          :color="getInterpretationStatusColor(gi.interpretationStatus)"
                          size="small"
                          variant="flat"
                        >
                          {{ gi.interpretationStatus }}
                        </v-chip>
                      </v-list-item-subtitle>
                    </v-list-item>

                    <div
                      v-if="gi.variantInterpretation.variationDescriptor.description"
                      class="px-0 mb-3"
                    >
                      <div class="font-weight-bold mb-2 text-subtitle-2">Description</div>
                      <div
                        class="text-body-2"
                        style="
                          white-space: normal;
                          word-break: break-word;
                          overflow-wrap: break-word;
                          width: 100%;
                          color: rgba(0, 0, 0, 0.6);
                        "
                      >
                        {{ gi.variantInterpretation.variationDescriptor.description }}
                      </div>
                    </div>
                  </div>
                </div>

                <v-divider
                  v-if="giIndex < interpretation.diagnosis.genomicInterpretations.length - 1"
                  class="my-2"
                />
              </div>
            </v-list>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-card-text>
  </v-card>
</template>

<script>
export default {
  name: 'InterpretationsCard',
  props: {
    interpretations: {
      type: Array,
      default: () => [],
    },
  },
  computed: {
    uniqueInterpretations() {
      // Filter out duplicate interpretations (keep only those with descriptive labels)
      // Remove interpretations with generic "HNF1B:variant" labels when better labels exist
      const filtered = this.interpretations.filter((interp) => {
        if (!interp.diagnosis?.genomicInterpretations) return false;

        const gi = interp.diagnosis.genomicInterpretations[0];
        const label = gi?.variantInterpretation?.variationDescriptor?.label;

        // Skip generic labels like "HNF1B:variant" or "GENE:variant"
        if (label && label.match(/^[A-Z0-9]+:variant$/i)) {
          return false;
        }

        return true;
      });

      return filtered;
    },
  },
  methods: {
    getVariantSummary(interpretation) {
      // Extract variant label from first genomic interpretation
      if (
        interpretation?.diagnosis?.genomicInterpretations &&
        interpretation.diagnosis.genomicInterpretations.length > 0
      ) {
        const gi = interpretation.diagnosis.genomicInterpretations[0];
        const label = gi.variantInterpretation?.variationDescriptor?.label;
        const gene = gi.variantInterpretation?.variationDescriptor?.geneContext?.symbol;

        if (label) {
          return label;
        } else if (gene) {
          return `${gene} variant`;
        }
      }
      return null;
    },

    getInterpretationStatusColor(status) {
      const colors = {
        CAUSATIVE: 'red',
        CONTRIBUTORY: 'orange',
        CANDIDATE: 'blue',
        UNCERTAIN_SIGNIFICANCE: 'grey',
        NO_KNOWN_DISEASE_RELATIONSHIP: 'grey',
        PATHOGENIC: 'red',
        LIKELY_PATHOGENIC: 'orange',
      };
      return colors[status] || 'grey';
    },

    getPathogenicityColor(classification) {
      const colors = {
        PATHOGENIC: 'red',
        LIKELY_PATHOGENIC: 'orange',
        UNCERTAIN_SIGNIFICANCE: 'grey',
        LIKELY_BENIGN: 'light-blue',
        BENIGN: 'green',
      };
      return colors[classification] || 'grey';
    },

    getActionabilityColor(actionability) {
      const colors = {
        ACTIONABLE: 'green',
        NOT_ACTIONABLE: 'grey',
        UNKNOWN_ACTIONABILITY: 'grey',
      };
      return colors[actionability] || 'grey';
    },
  },
};
</script>
