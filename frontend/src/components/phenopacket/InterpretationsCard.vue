<!-- src/components/phenopacket/InterpretationsCard.vue -->
<template>
  <v-card outlined>
    <v-card-title class="text-h6 bg-purple-lighten-5">
      <v-icon left color="deep-purple">
        mdi-dna
      </v-icon>
      Genomic Interpretations ({{ interpretations.length }})
    </v-card-title>
    <v-card-text>
      <v-alert v-if="interpretations.length === 0" type="info" density="compact">
        No genomic interpretations recorded
      </v-alert>

      <v-expansion-panels v-else accordion>
        <v-expansion-panel v-for="(interpretation, index) in interpretations" :key="index">
          <v-expansion-panel-title>
            <v-icon left color="deep-purple">
              mdi-dna
            </v-icon>
            <span class="font-weight-bold mr-2">{{ interpretation.id }}</span>
            <v-chip
              :color="getProgressStatusColor(interpretation.progressStatus)"
              size="small"
              variant="flat"
            >
              {{ interpretation.progressStatus }}
            </v-chip>
          </v-expansion-panel-title>

          <v-expansion-panel-text>
            <v-list v-if="interpretation.diagnosis">
              <v-list-item v-if="interpretation.diagnosis.disease">
                <v-list-item-title class="font-weight-bold">
                  Disease
                </v-list-item-title>
                <v-list-item-subtitle>
                  <v-chip color="red" size="small" class="mr-1">
                    {{ interpretation.diagnosis.disease.id }}
                  </v-chip>
                  {{ interpretation.diagnosis.disease.label }}
                </v-list-item-subtitle>
              </v-list-item>

              <v-divider class="my-2" />

              <v-list-item-title class="font-weight-bold mb-2">
                Genomic Interpretations
              </v-list-item-title>

              <v-card
                v-for="(gi, giIndex) in interpretation.diagnosis.genomicInterpretations"
                :key="giIndex"
                outlined
                class="mb-2"
              >
                <v-card-text>
                  <div class="mb-2">
                    <strong>Subject:</strong> {{ gi.subjectOrBiosampleId }}
                  </div>
                  <div class="mb-2">
                    <strong>Status:</strong>
                    <v-chip
                      :color="getInterpretationStatusColor(gi.interpretationStatus)"
                      size="small"
                      variant="flat"
                    >
                      {{ gi.interpretationStatus }}
                    </v-chip>
                  </div>

                  <v-divider class="my-2" />

                  <div v-if="gi.variantInterpretation" class="mt-2">
                    <v-list-item-title class="font-weight-bold mb-2">
                      Variant Details
                    </v-list-item-title>

                    <div v-if="gi.variantInterpretation.variationDescriptor">
                      <div class="mb-2">
                        <strong>Label:</strong>
                        {{ gi.variantInterpretation.variationDescriptor.label || 'N/A' }}
                      </div>

                      <div
                        v-if="gi.variantInterpretation.variationDescriptor.geneContext"
                        class="mb-2"
                      >
                        <strong>Gene:</strong>
                        <v-chip color="blue" size="small" class="mr-1">
                          {{ gi.variantInterpretation.variationDescriptor.geneContext.valueId }}
                        </v-chip>
                        {{ gi.variantInterpretation.variationDescriptor.geneContext.symbol }}
                      </div>

                      <div
                        v-if="gi.variantInterpretation.variationDescriptor.vcfRecord"
                        class="mb-2"
                      >
                        <strong>VCF:</strong>
                        {{ gi.variantInterpretation.variationDescriptor.vcfRecord.genomeAssembly }}
                        - Chr{{ gi.variantInterpretation.variationDescriptor.vcfRecord.chrom }}:{{
                          gi.variantInterpretation.variationDescriptor.vcfRecord.pos
                        }}
                        {{ gi.variantInterpretation.variationDescriptor.vcfRecord.ref }} >
                        {{ gi.variantInterpretation.variationDescriptor.vcfRecord.alt }}
                      </div>
                    </div>

                    <div
                      v-if="gi.variantInterpretation.acmgPathogenicityClassification"
                      class="mb-2"
                    >
                      <strong>ACMG Classification:</strong>
                      <v-chip
                        :color="
                          getPathogenicityColor(
                            gi.variantInterpretation.acmgPathogenicityClassification,
                          )
                        "
                        size="small"
                        variant="flat"
                        class="ml-1"
                      >
                        {{ gi.variantInterpretation.acmgPathogenicityClassification }}
                      </v-chip>
                    </div>

                    <div
                      v-if="gi.variantInterpretation.therapeuticActionability"
                      class="mb-2"
                    >
                      <strong>Therapeutic Actionability:</strong>
                      <v-chip
                        :color="
                          getActionabilityColor(gi.variantInterpretation.therapeuticActionability)
                        "
                        size="small"
                        variant="flat"
                        class="ml-1"
                      >
                        {{ gi.variantInterpretation.therapeuticActionability }}
                      </v-chip>
                    </div>
                  </div>
                </v-card-text>
              </v-card>
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
  methods: {
    getProgressStatusColor(status) {
      const colors = {
        SOLVED: 'green',
        UNSOLVED: 'orange',
        IN_PROGRESS: 'blue',
        UNKNOWN: 'grey',
      };
      return colors[status] || 'grey';
    },

    getInterpretationStatusColor(status) {
      const colors = {
        CAUSATIVE: 'red',
        CONTRIBUTORY: 'orange',
        CANDIDATE: 'blue',
        UNCERTAIN_SIGNIFICANCE: 'grey',
        NO_KNOWN_DISEASE_RELATIONSHIP: 'grey',
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
