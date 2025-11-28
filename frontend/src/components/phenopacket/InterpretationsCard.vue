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
                    <!-- Variant ID with link -->
                    <v-list-item class="px-0">
                      <v-list-item-title class="font-weight-bold"> Variant </v-list-item-title>
                      <v-list-item-subtitle>
                        <v-chip
                          v-if="gi.variantInterpretation.variationDescriptor.id"
                          :to="`/variants/${encodeURIComponent(gi.variantInterpretation.variationDescriptor.id)}`"
                          color="blue-lighten-3"
                          size="small"
                          variant="flat"
                          link
                        >
                          <v-icon left size="small">mdi-dna</v-icon>
                          View Details
                        </v-chip>
                      </v-list-item-subtitle>
                    </v-list-item>

                    <!-- Variant Type -->
                    <v-list-item class="px-0">
                      <v-list-item-title class="font-weight-bold"> Type </v-list-item-title>
                      <v-list-item-subtitle>
                        <v-chip
                          :color="
                            getVariantTypeColor(
                              getVariantTypeFromDescriptor(
                                gi.variantInterpretation.variationDescriptor
                              )
                            )
                          "
                          size="small"
                          variant="flat"
                        >
                          {{
                            getVariantTypeFromDescriptor(
                              gi.variantInterpretation.variationDescriptor
                            )
                          }}
                        </v-chip>
                      </v-list-item-subtitle>
                    </v-list-item>

                    <!-- Size (for CNVs) -->
                    <v-list-item
                      v-if="
                        getVariantSizeFromDescriptor(gi.variantInterpretation.variationDescriptor)
                      "
                      class="px-0"
                    >
                      <v-list-item-title class="font-weight-bold"> Size </v-list-item-title>
                      <v-list-item-subtitle>
                        {{
                          getVariantSizeFromDescriptor(gi.variantInterpretation.variationDescriptor)
                        }}
                      </v-list-item-subtitle>
                    </v-list-item>

                    <!-- CNV-specific details: Chromosome, Start, End -->
                    <template
                      v-if="
                        getCNVDetailsFromDescriptor(gi.variantInterpretation.variationDescriptor)
                      "
                    >
                      <v-list-item class="px-0">
                        <v-list-item-title class="font-weight-bold"> Chromosome </v-list-item-title>
                        <v-list-item-subtitle>
                          chr{{
                            getCNVDetailsFromDescriptor(
                              gi.variantInterpretation.variationDescriptor
                            ).chromosome
                          }}
                        </v-list-item-subtitle>
                      </v-list-item>

                      <v-list-item class="px-0">
                        <v-list-item-title class="font-weight-bold">
                          Start Position
                        </v-list-item-title>
                        <v-list-item-subtitle>
                          {{
                            formatPosition(
                              getCNVDetailsFromDescriptor(
                                gi.variantInterpretation.variationDescriptor
                              ).start
                            )
                          }}
                        </v-list-item-subtitle>
                      </v-list-item>

                      <v-list-item class="px-0">
                        <v-list-item-title class="font-weight-bold">
                          End Position
                        </v-list-item-title>
                        <v-list-item-subtitle>
                          {{
                            formatPosition(
                              getCNVDetailsFromDescriptor(
                                gi.variantInterpretation.variationDescriptor
                              ).end
                            )
                          }}
                        </v-list-item-subtitle>
                      </v-list-item>
                    </template>

                    <!-- HG38 coordinates -->
                    <v-list-item
                      v-if="getHG38FromDescriptor(gi.variantInterpretation.variationDescriptor)"
                      class="px-0"
                    >
                      <v-list-item-title class="font-weight-bold"> HG38 </v-list-item-title>
                      <v-list-item-subtitle>
                        {{ getHG38FromDescriptor(gi.variantInterpretation.variationDescriptor) }}
                      </v-list-item-subtitle>
                    </v-list-item>

                    <!-- Transcript (HGVS c. notation) -->
                    <v-list-item
                      v-if="
                        getTranscriptFromDescriptor(gi.variantInterpretation.variationDescriptor)
                      "
                      class="px-0"
                    >
                      <v-list-item-title class="font-weight-bold"> Transcript </v-list-item-title>
                      <v-list-item-subtitle>
                        {{
                          getTranscriptFromDescriptor(gi.variantInterpretation.variationDescriptor)
                        }}
                      </v-list-item-subtitle>
                    </v-list-item>

                    <!-- Gene -->
                    <v-list-item
                      v-if="gi.variantInterpretation.variationDescriptor.geneContext"
                      class="px-0"
                    >
                      <v-list-item-title class="font-weight-bold"> Gene </v-list-item-title>
                      <v-list-item-subtitle>
                        <a
                          :href="`https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/${gi.variantInterpretation.variationDescriptor.geneContext.valueId}`"
                          target="_blank"
                          rel="noopener noreferrer"
                          class="gene-link"
                        >
                          {{ gi.variantInterpretation.variationDescriptor.geneContext.symbol }}
                        </a>
                        <span class="text-caption text-grey">
                          ({{ gi.variantInterpretation.variationDescriptor.geneContext.valueId }})
                        </span>
                      </v-list-item-subtitle>
                    </v-list-item>

                    <!-- Classification -->
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

                    <!-- Molecular Consequence -->
                    <v-list-item
                      v-if="
                        getMolecularConsequenceFromDescriptor(
                          gi.variantInterpretation.variationDescriptor
                        )
                      "
                      class="px-0"
                    >
                      <v-list-item-title class="font-weight-bold">
                        Molecular Consequence
                      </v-list-item-title>
                      <v-list-item-subtitle>
                        <v-chip color="purple-lighten-3" size="small" variant="flat">
                          {{
                            getMolecularConsequenceFromDescriptor(
                              gi.variantInterpretation.variationDescriptor
                            )
                          }}
                        </v-chip>
                      </v-list-item-subtitle>
                    </v-list-item>
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
import { getVariantTypeColor } from '@/utils/colors';
import { getVariantType, isCNV, getCNVDetails, getVariantSize } from '@/utils/variants';
import { extractCNotation, extractPNotation } from '@/utils/hgvs';

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
    getVariantTypeColor,

    /**
     * Convert variationDescriptor to variant-like object for utility functions.
     */
    descriptorToVariant(descriptor) {
      if (!descriptor) return null;

      // Extract HGVS expressions
      const expressions = descriptor.expressions || [];
      const hgvsC = expressions.find((e) => e.syntax === 'hgvs.c');
      const hgvsP = expressions.find((e) => e.syntax === 'hgvs.p');

      // Extract HG38 coordinates from extensions
      const extensions = descriptor.extensions || [];
      const coordsExt = extensions.find((e) => e.name === 'coordinates');
      const coords = coordsExt?.value || {};

      // Build HG38 string from coordinates if available
      let hg38 = null;
      if (coords.chromosome && coords.start && coords.end) {
        const chr = coords.chromosome.replace('chr', '');
        // Determine SV type from molecularAttributes or label
        const molecularAttrs = descriptor.molecularAttributes || {};
        const ontologyClass = molecularAttrs.ontologyClass || {};
        let svType = '';
        if (ontologyClass.label?.includes('deletion') || descriptor.label?.includes('deletion')) {
          svType = 'DEL';
        } else if (
          ontologyClass.label?.includes('duplication') ||
          descriptor.label?.includes('duplication')
        ) {
          svType = 'DUP';
        }
        hg38 = `${chr}:${coords.start}-${coords.end}:${svType}`;
      }

      // Determine variant type from molecularAttributes
      const molecularAttrs = descriptor.molecularAttributes || {};
      const ontologyClass = molecularAttrs.ontologyClass || {};
      let variantType = null;
      if (ontologyClass.label) {
        if (ontologyClass.label.includes('deletion')) variantType = 'deletion';
        else if (ontologyClass.label.includes('duplication')) variantType = 'duplication';
      }

      return {
        hg38,
        transcript: hgvsC?.value || null,
        protein: hgvsP?.value || null,
        variant_type: variantType,
        geneSymbol: descriptor.geneContext?.symbol || null,
      };
    },

    /**
     * Get variant type from variationDescriptor.
     */
    getVariantTypeFromDescriptor(descriptor) {
      const variant = this.descriptorToVariant(descriptor);
      if (!variant) return 'Unknown';

      // Use utility function with specificCNVType for detail view
      return getVariantType(variant, { specificCNVType: true });
    },

    /**
     * Get formatted variant size from variationDescriptor.
     */
    getVariantSizeFromDescriptor(descriptor) {
      // First try to get size from coordinates extension
      const extensions = descriptor?.extensions || [];
      const coordsExt = extensions.find((e) => e.name === 'coordinates');
      const lengthBp = coordsExt?.value?.length;

      if (lengthBp) {
        if (lengthBp >= 1000000) {
          return `${(lengthBp / 1000000).toFixed(2)} Mb`;
        } else if (lengthBp >= 1000) {
          return `${(lengthBp / 1000).toFixed(2)} kb`;
        } else {
          return `${lengthBp.toLocaleString()} bp`;
        }
      }

      // Fall back to utility function
      const variant = this.descriptorToVariant(descriptor);
      if (!variant) return null;

      return getVariantSize(variant, { formatted: true });
    },

    /**
     * Get CNV details (chromosome, start, end) from variationDescriptor.
     */
    getCNVDetailsFromDescriptor(descriptor) {
      // First check if this is a CNV
      const variant = this.descriptorToVariant(descriptor);
      if (!variant || !isCNV(variant)) return null;

      // Get details from coordinates extension
      const extensions = descriptor?.extensions || [];
      const coordsExt = extensions.find((e) => e.name === 'coordinates');
      const coords = coordsExt?.value || {};

      if (coords.chromosome && coords.start && coords.end) {
        return {
          chromosome: coords.chromosome.replace('chr', ''),
          start: coords.start,
          end: coords.end,
        };
      }

      // Fall back to utility function
      return getCNVDetails(variant);
    },

    /**
     * Get HG38 coordinates from variationDescriptor.
     */
    getHG38FromDescriptor(descriptor) {
      const extensions = descriptor?.extensions || [];
      const coordsExt = extensions.find((e) => e.name === 'coordinates');
      const coords = coordsExt?.value || {};

      if (coords.chromosome && coords.start && coords.end) {
        const chr = coords.chromosome.replace('chr', '');
        // Determine SV type
        const molecularAttrs = descriptor.molecularAttributes || {};
        const ontologyClass = molecularAttrs.ontologyClass || {};
        let svType = '';
        if (ontologyClass.label?.includes('deletion') || descriptor.label?.includes('deletion')) {
          svType = ':DEL';
        } else if (
          ontologyClass.label?.includes('duplication') ||
          descriptor.label?.includes('duplication')
        ) {
          svType = ':DUP';
        }
        return `${chr}:${coords.start}-${coords.end}${svType}`;
      }

      // For non-CNVs, try to get from HGVS.g expression
      const expressions = descriptor?.expressions || [];
      const hgvsG = expressions.find((e) => e.syntax === 'hgvs.g');
      if (hgvsG?.value) {
        return hgvsG.value;
      }

      return null;
    },

    /**
     * Get transcript (HGVS c. notation) from variationDescriptor.
     */
    getTranscriptFromDescriptor(descriptor) {
      const expressions = descriptor?.expressions || [];
      const hgvsC = expressions.find((e) => e.syntax === 'hgvs.c');
      return hgvsC?.value || null;
    },

    /**
     * Get molecular consequence from variationDescriptor.
     */
    getMolecularConsequenceFromDescriptor(descriptor) {
      // Check molecularAttributes.ontologyClass first
      const molecularAttrs = descriptor?.molecularAttributes || {};
      const ontologyClass = molecularAttrs.ontologyClass || {};

      if (ontologyClass.label) {
        // Map SO terms to human-readable labels
        const label = ontologyClass.label.toLowerCase();
        if (label.includes('copy number loss')) return 'Copy Number Loss';
        if (label.includes('copy number gain')) return 'Copy Number Gain';
        if (label.includes('deletion')) return 'Copy Number Loss';
        if (label.includes('duplication')) return 'Copy Number Gain';
        if (label.includes('frameshift')) return 'Frameshift';
        if (label.includes('nonsense') || label.includes('stop_gained')) return 'Nonsense';
        if (label.includes('missense')) return 'Missense';
        if (label.includes('splice_donor')) return 'Splice Donor';
        if (label.includes('splice_acceptor')) return 'Splice Acceptor';
        if (label.includes('splice')) return 'Splice Site';
        if (label.includes('synonymous')) return 'Synonymous';
        if (label.includes('intron')) return 'Intronic Variant';

        // Return the label as-is if no mapping
        return ontologyClass.label;
      }

      // Fall back to computing from protein/transcript notation
      const expressions = descriptor?.expressions || [];
      const hgvsP = expressions.find((e) => e.syntax === 'hgvs.p');
      const hgvsC = expressions.find((e) => e.syntax === 'hgvs.c');

      if (hgvsP?.value) {
        const pNotation = extractPNotation(hgvsP.value);
        if (pNotation && pNotation !== '-') {
          if (pNotation.includes('fs')) return 'Frameshift';
          if (pNotation.includes('Ter') || pNotation.includes('*')) return 'Nonsense';
          if (pNotation.match(/p\.[A-Z][a-z]{2}\d+[A-Z][a-z]{2}/)) return 'Missense';
          if (pNotation.includes('del') && !pNotation.includes('fs')) return 'In-frame Deletion';
          if (pNotation.includes('ins') && !pNotation.includes('fs')) return 'In-frame Insertion';
          if (pNotation.includes('=')) return 'Synonymous';
          return 'Coding Sequence Variant';
        }
      }

      if (hgvsC?.value) {
        const cNotation = extractCNotation(hgvsC.value);
        if (cNotation && cNotation !== '-') {
          const spliceMatch = cNotation.match(/([+-])(\d+)/);
          if (spliceMatch) {
            const sign = spliceMatch[1];
            const position = parseInt(spliceMatch[2], 10);
            if (sign === '+' && position >= 1 && position <= 6) return 'Splice Donor';
            if (sign === '-' && position >= 1 && position <= 3) return 'Splice Acceptor';
            return 'Intronic Variant';
          }
          return 'Coding Sequence Variant';
        }
      }

      return null;
    },

    /**
     * Format position with thousand separators.
     */
    formatPosition(pos) {
      return parseInt(pos).toLocaleString();
    },

    getVariantSummary(interpretation) {
      // Extract variant label from first genomic interpretation
      if (
        interpretation?.diagnosis?.genomicInterpretations &&
        interpretation.diagnosis.genomicInterpretations.length > 0
      ) {
        const gi = interpretation.diagnosis.genomicInterpretations[0];
        const descriptor = gi.variantInterpretation?.variationDescriptor;
        const gene = descriptor?.geneContext?.symbol;

        // For CNVs, show type and size instead of dbVar label
        if (descriptor) {
          const variantType = this.getVariantTypeFromDescriptor(descriptor);
          const size = this.getVariantSizeFromDescriptor(descriptor);

          if (variantType === 'deletion' || variantType === 'duplication') {
            const typeLabel = variantType.charAt(0).toUpperCase() + variantType.slice(1);
            return size ? `${typeLabel} (${size})` : typeLabel;
          }

          // For non-CNVs, try transcript notation
          const transcript = this.getTranscriptFromDescriptor(descriptor);
          if (transcript) {
            const cNotation = extractCNotation(transcript);
            if (cNotation && cNotation !== '-') {
              return gene ? `${gene} ${cNotation}` : cNotation;
            }
          }
        }

        // Fall back to gene name
        if (gene) {
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
  },
};
</script>

<style scoped>
.gene-link {
  color: #1976d2;
  text-decoration: none;
  font-weight: 500;
}

.gene-link:hover {
  text-decoration: underline;
}
</style>
