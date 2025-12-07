<!-- src/components/phenopacket/InterpretationsCard.vue -->
<template>
  <v-card outlined class="interpretation-card">
    <v-card-title :class="['text-subtitle-1', cardHeader.titlePadding, cardHeader.bgColor]">
      <v-icon left :color="cardHeader.iconColor" size="small">
        {{ cardHeader.icon }}
      </v-icon>
      {{ cardHeader.title }} ({{ uniqueInterpretations.length }})
    </v-card-title>
    <v-card-text class="pa-2">
      <v-alert v-if="uniqueInterpretations.length === 0" type="info" density="compact">
        No genomic interpretations recorded
      </v-alert>

      <!-- Inline variant display - no expansion panels -->
      <div v-else class="variants-container">
        <div
          v-for="(interpretation, index) in uniqueInterpretations"
          :key="index"
          class="variant-item"
        >
          <!-- Row 1: Primary info - type, gene, notation, classification -->
          <div class="variant-primary-row">
            <!-- Variant type chip -->
            <v-chip
              :color="getVariantTypeColor(getVariantTypeFromInterpretation(interpretation))"
              size="x-small"
              variant="flat"
              label
              class="variant-type-chip"
            >
              {{ getVariantTypeFromInterpretation(interpretation) }}
            </v-chip>

            <!-- Gene symbol -->
            <span v-if="getGeneSymbol(interpretation)" class="gene-symbol">
              {{ getGeneSymbol(interpretation) }}
            </span>

            <!-- c. notation -->
            <code v-if="getCNotation(interpretation)" class="hgvs-notation c-notation">
              {{ getCNotation(interpretation) }}
            </code>

            <!-- p. notation -->
            <code v-if="getPNotation(interpretation)" class="hgvs-notation p-notation">
              {{ getPNotation(interpretation) }}
            </code>

            <!-- Spacer -->
            <div class="flex-grow-1" />

            <!-- Classification badge -->
            <v-chip
              :color="getStatusColor(getInterpretationStatus(interpretation))"
              size="x-small"
              variant="flat"
              class="classification-chip"
            >
              {{ getStatusLabel(getInterpretationStatus(interpretation)) }}
            </v-chip>

            <!-- View details button -->
            <v-btn
              v-if="getVariantId(interpretation)"
              :to="`/variants/${encodeURIComponent(getVariantId(interpretation))}`"
              color="deep-purple"
              variant="text"
              size="x-small"
              icon="mdi-arrow-right"
              density="compact"
              class="ml-1"
            />
          </div>

          <!-- Row 2: Secondary info - coordinates, size, consequence -->
          <div v-if="hasSecondaryDetails(interpretation)" class="variant-secondary-row">
            <span
              v-if="getInterpretationDetails(interpretation)?.coordinates"
              class="variant-detail"
            >
              <v-icon size="x-small" class="mr-1">mdi-map-marker</v-icon>
              <code>{{ getInterpretationDetails(interpretation).coordinates }}</code>
            </span>

            <span v-if="getInterpretationDetails(interpretation)?.size" class="variant-detail">
              <v-icon size="x-small" class="mr-1">mdi-ruler</v-icon>
              {{ getInterpretationDetails(interpretation).size }}
            </span>

            <v-chip
              v-if="getInterpretationDetails(interpretation)?.consequence"
              size="x-small"
              color="purple-lighten-4"
              variant="flat"
              class="consequence-chip"
            >
              {{ getInterpretationDetails(interpretation).consequence }}
            </v-chip>
          </div>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
import { getVariantTypeColor } from '@/utils/colors';
import {
  CARD_HEADERS,
  TYPOGRAPHY,
  COLORS,
  CHIP_SIZES,
  getInterpretationStatusColor,
  getInterpretationStatusLabel,
} from '@/utils/cardStyles';
import { getVariantType, getVariantSize } from '@/utils/variants';
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
    cardHeader() {
      return {
        ...CARD_HEADERS.interpretations,
        titlePadding: 'py-2',
      };
    },

    // Expose typography tokens to template for CSS variable injection
    typography() {
      return TYPOGRAPHY;
    },

    colors() {
      return COLORS;
    },

    chipSize() {
      return CHIP_SIZES.dense; // Use x-small for dense interpretation display
    },

    uniqueInterpretations() {
      const filtered = this.interpretations.filter((interp) => {
        if (!interp.diagnosis?.genomicInterpretations) return false;

        const gi = interp.diagnosis.genomicInterpretations[0];
        const label = gi?.variantInterpretation?.variationDescriptor?.label;

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
    getStatusColor: getInterpretationStatusColor,
    getStatusLabel: getInterpretationStatusLabel,

    getInterpretationStatus(interpretation) {
      const gi = interpretation.diagnosis?.genomicInterpretations?.[0];
      return gi?.interpretationStatus || 'UNKNOWN';
    },

    getVariantId(interpretation) {
      const gi = interpretation.diagnosis?.genomicInterpretations?.[0];
      return gi?.variantInterpretation?.variationDescriptor?.id || null;
    },

    getVariantTypeFromInterpretation(interpretation) {
      const gi = interpretation.diagnosis?.genomicInterpretations?.[0];
      if (!gi?.variantInterpretation?.variationDescriptor) return 'Unknown';

      return this.getVariantTypeFromDescriptor(gi.variantInterpretation.variationDescriptor);
    },

    descriptorToVariant(descriptor) {
      if (!descriptor) return null;

      const expressions = descriptor.expressions || [];
      const hgvsC = expressions.find((e) => e.syntax === 'hgvs.c');
      const hgvsP = expressions.find((e) => e.syntax === 'hgvs.p');

      const extensions = descriptor.extensions || [];
      const coordsExt = extensions.find((e) => e.name === 'coordinates');
      const coords = coordsExt?.value || {};

      let hg38 = null;
      if (coords.chromosome && coords.start && coords.end) {
        const chr = coords.chromosome.replace('chr', '');
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

    getVariantTypeFromDescriptor(descriptor) {
      const variant = this.descriptorToVariant(descriptor);
      if (!variant) return 'Unknown';

      return getVariantType(variant, { specificCNVType: true });
    },

    getVariantSizeFromDescriptor(descriptor) {
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

      const variant = this.descriptorToVariant(descriptor);
      if (!variant) return null;

      return getVariantSize(variant, { formatted: true });
    },

    getHG38FromDescriptor(descriptor) {
      const extensions = descriptor?.extensions || [];
      const coordsExt = extensions.find((e) => e.name === 'coordinates');
      const coords = coordsExt?.value || {};

      if (coords.chromosome && coords.start && coords.end) {
        const chr = coords.chromosome.replace('chr', '');
        return `${chr}:${coords.start.toLocaleString()}-${coords.end.toLocaleString()}`;
      }

      const expressions = descriptor?.expressions || [];
      const hgvsG = expressions.find((e) => e.syntax === 'hgvs.g');
      if (hgvsG?.value) {
        return hgvsG.value;
      }

      return null;
    },

    getMolecularConsequenceFromDescriptor(descriptor) {
      const molecularAttrs = descriptor?.molecularAttributes || {};
      const ontologyClass = molecularAttrs.ontologyClass || {};

      if (ontologyClass.label) {
        const label = ontologyClass.label.toLowerCase();
        if (label.includes('copy number loss')) return 'CNV Loss';
        if (label.includes('copy number gain')) return 'CNV Gain';
        if (label.includes('deletion')) return 'Deletion';
        if (label.includes('duplication')) return 'Duplication';
        if (label.includes('frameshift')) return 'Frameshift';
        if (label.includes('nonsense') || label.includes('stop_gained')) return 'Nonsense';
        if (label.includes('missense')) return 'Missense';
        if (label.includes('splice_donor')) return 'Splice Donor';
        if (label.includes('splice_acceptor')) return 'Splice Acceptor';
        if (label.includes('splice')) return 'Splice';
        if (label.includes('synonymous')) return 'Synonymous';
        if (label.includes('intron')) return 'Intronic';

        return ontologyClass.label;
      }

      const expressions = descriptor?.expressions || [];
      const hgvsP = expressions.find((e) => e.syntax === 'hgvs.p');
      const hgvsC = expressions.find((e) => e.syntax === 'hgvs.c');

      if (hgvsP?.value) {
        const pNotation = extractPNotation(hgvsP.value);
        if (pNotation && pNotation !== '-') {
          if (pNotation.includes('fs')) return 'Frameshift';
          if (pNotation.includes('Ter') || pNotation.includes('*')) return 'Nonsense';
          if (pNotation.match(/p\.[A-Z][a-z]{2}\d+[A-Z][a-z]{2}/)) return 'Missense';
          if (pNotation.includes('del') && !pNotation.includes('fs')) return 'In-frame Del';
          if (pNotation.includes('ins') && !pNotation.includes('fs')) return 'In-frame Ins';
          if (pNotation.includes('=')) return 'Synonymous';
          return 'Coding';
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
            return 'Intronic';
          }
          return 'Coding';
        }
      }

      return null;
    },

    getInterpretationDetails(interpretation) {
      const gi = interpretation.diagnosis?.genomicInterpretations?.[0];
      const descriptor = gi?.variantInterpretation?.variationDescriptor;
      if (!descriptor) return null;

      return {
        coordinates: this.getHG38FromDescriptor(descriptor),
        size: this.getVariantSizeFromDescriptor(descriptor),
        consequence: this.getMolecularConsequenceFromDescriptor(descriptor),
      };
    },

    hasSecondaryDetails(interpretation) {
      const details = this.getInterpretationDetails(interpretation);
      if (!details) return false;
      return details.coordinates || details.size || details.consequence;
    },

    getGeneSymbol(interpretation) {
      const gi = interpretation.diagnosis?.genomicInterpretations?.[0];
      return gi?.variantInterpretation?.variationDescriptor?.geneContext?.symbol || null;
    },

    getCNotation(interpretation) {
      const gi = interpretation.diagnosis?.genomicInterpretations?.[0];
      const expressions = gi?.variantInterpretation?.variationDescriptor?.expressions || [];
      const hgvsC = expressions.find((e) => e.syntax === 'hgvs.c');
      if (hgvsC?.value) {
        return extractCNotation(hgvsC.value);
      }
      return null;
    },

    getPNotation(interpretation) {
      const gi = interpretation.diagnosis?.genomicInterpretations?.[0];
      const expressions = gi?.variantInterpretation?.variationDescriptor?.expressions || [];
      const hgvsP = expressions.find((e) => e.syntax === 'hgvs.p');
      if (hgvsP?.value) {
        const pNotation = extractPNotation(hgvsP.value);
        return pNotation && pNotation !== '-' ? pNotation : null;
      }
      return null;
    },

    getVariantSummary(interpretation) {
      if (
        interpretation?.diagnosis?.genomicInterpretations &&
        interpretation.diagnosis.genomicInterpretations.length > 0
      ) {
        const gi = interpretation.diagnosis.genomicInterpretations[0];
        const descriptor = gi.variantInterpretation?.variationDescriptor;
        const gene = descriptor?.geneContext?.symbol;

        if (descriptor) {
          const variantType = this.getVariantTypeFromDescriptor(descriptor);
          const size = this.getVariantSizeFromDescriptor(descriptor);

          if (variantType === 'deletion' || variantType === 'duplication') {
            const typeLabel = variantType.charAt(0).toUpperCase() + variantType.slice(1);
            return size ? `${typeLabel} (${size})` : typeLabel;
          }

          const expressions = descriptor.expressions || [];
          const hgvsC = expressions.find((e) => e.syntax === 'hgvs.c');
          if (hgvsC?.value) {
            const cNotation = extractCNotation(hgvsC.value);
            if (cNotation && cNotation !== '-') {
              return gene ? `${gene} ${cNotation}` : cNotation;
            }
          }
        }

        if (gene) {
          return `${gene} variant`;
        }
      }
      return null;
    },
  },
};
</script>

<style scoped>
/**
 * Typography tokens applied via CSS custom properties.
 * Values sourced from cardStyles.js TYPOGRAPHY and COLORS.
 */
.interpretation-card {
  /* Typography tokens */
  --font-size-xs: 10px;
  --font-size-sm: 11px;
  --font-size-md: 13px;
  --font-mono: 'Roboto Mono', 'Consolas', 'Monaco', monospace;

  /* Color tokens */
  --color-text-primary: rgba(0, 0, 0, 0.87);
  --color-text-secondary: rgba(0, 0, 0, 0.6);
  --color-gene: rgb(var(--v-theme-deep-purple));
  --color-c-notation: rgb(var(--v-theme-blue-darken-2));
  --color-p-notation: rgb(var(--v-theme-green-darken-2));
  --color-bg-code: rgba(0, 0, 0, 0.06);
  --color-bg-c-notation: rgba(33, 150, 243, 0.1);
  --color-bg-p-notation: rgba(76, 175, 80, 0.1);
  --color-accent: rgb(var(--v-theme-deep-purple));

  height: 100%;
  display: flex;
  flex-direction: column;
}

.variants-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.variant-item {
  background: rgba(103, 58, 183, 0.04);
  border-radius: 8px;
  padding: 10px 12px;
  transition: background-color 0.15s ease;
}

.variant-item:hover {
  background: rgba(103, 58, 183, 0.08);
}

/* Row 1: Primary info - type, gene, notation, classification */
.variant-primary-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* Row 2: Secondary info - coordinates, size, consequence */
.variant-secondary-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed rgba(103, 58, 183, 0.12);
}

.variant-type-chip {
  flex-shrink: 0;
}

.gene-symbol {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--color-gene, #512da8);
}

.hgvs-notation {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  background: var(--color-bg-code);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--color-text-primary);
}

.c-notation {
  background: var(--color-bg-c-notation);
  color: var(--color-c-notation, #1565c0);
}

.p-notation {
  background: var(--color-bg-p-notation);
  color: var(--color-p-notation, #2e7d32);
}

.variant-detail {
  display: inline-flex;
  align-items: center;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.variant-detail code {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  background: var(--color-bg-code);
  padding: 2px 5px;
  border-radius: 3px;
}

.classification-chip {
  flex-shrink: 0;
}

.consequence-chip {
  flex-shrink: 0;
}

.flex-grow-1 {
  flex-grow: 1;
}

@media (max-width: 600px) {
  .variant-primary-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }

  .variant-secondary-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }

  .flex-grow-1 {
    display: none;
  }
}
</style>
