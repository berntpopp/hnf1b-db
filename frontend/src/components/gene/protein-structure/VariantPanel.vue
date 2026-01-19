<!-- Variant Panel Component -->
<!-- Variant list with filtering and sorting for showAllVariants mode -->
<template>
  <div class="variant-panel">
    <div class="variant-panel-header">
      <span class="text-subtitle-2">Variants in Structure</span>
      <v-chip size="x-small" color="primary" class="ml-2">
        {{ filteredAndSortedVariants.length }}
        <template v-if="filteredAndSortedVariants.length !== variants.length">
          / {{ variants.length }}
        </template>
      </v-chip>
    </div>

    <!-- Filter and Sort Controls -->
    <div class="variant-panel-controls">
      <!-- Sort Control -->
      <v-select
        v-model="sortBy"
        :items="sortOptions"
        label="Sort by"
        density="compact"
        hide-details
        variant="outlined"
        class="sort-select"
      />

      <!-- Pathogenicity Filter -->
      <v-select
        v-model="filterPathogenicity"
        :items="pathogenicityOptions"
        label="Pathogenicity"
        density="compact"
        hide-details
        variant="outlined"
        clearable
        class="filter-select"
      />

      <!-- Distance Filter -->
      <v-select
        v-model="filterDistance"
        :items="distanceOptions"
        label="DNA Distance"
        density="compact"
        hide-details
        variant="outlined"
        clearable
        class="filter-select"
      />
    </div>

    <v-list density="compact" class="variant-list">
      <v-list-item
        v-for="variant in filteredAndSortedVariants"
        :key="variant.variant_id"
        :class="{
          'variant-item-active': selectedId === variant.variant_id,
          'variant-item-hover': hoveredId === variant.variant_id,
        }"
        @click="$emit('select', variant)"
        @mouseenter="$emit('hover', variant)"
        @mouseleave="$emit('unhover')"
      >
        <template #prepend>
          <v-avatar :color="getVariantChipColor(variant)" size="28">
            <span class="text-white text-caption">{{ extractAAPosition(variant) }}</span>
          </v-avatar>
        </template>
        <v-list-item-title class="text-body-2">
          {{ getVariantLabel(variant) }}
        </v-list-item-title>
        <v-list-item-subtitle class="text-caption d-flex align-center">
          <span>{{ variant.classificationVerdict || 'Unknown' }}</span>
          <v-chip
            v-if="getVariantDistanceCategory(variant)"
            size="x-small"
            :color="getDistanceChipColor(getVariantDistanceCategory(variant))"
            class="ml-2"
          >
            {{ getVariantDistanceFormatted(variant) }}
          </v-chip>
        </v-list-item-subtitle>
      </v-list-item>
    </v-list>
    <div v-if="filteredAndSortedVariants.length === 0" class="text-center py-4 text-grey">
      <v-icon size="large" color="grey-lighten-1">mdi-alert-circle-outline</v-icon>
      <div class="text-caption mt-1">
        {{ variants.length === 0 ? 'No variants in structure range' : 'No variants match filters' }}
      </div>
      <v-btn
        v-if="variants.length > 0 && (filterPathogenicity || filterDistance)"
        size="x-small"
        variant="text"
        color="primary"
        class="mt-2"
        @click="clearFilters"
      >
        Clear Filters
      </v-btn>
    </div>
  </div>
</template>

<script>
import { getPathogenicityColor, getPathogenicityScore } from '@/utils/colors';
import { extractAAPosition as extractAAPositionUtil } from '@/utils/proteinDomains';
import { extractPNotation } from '@/utils/hgvs';
import './styles.css';

export default {
  name: 'VariantPanel',
  props: {
    /** All variants in structure range */
    variants: {
      type: Array,
      required: true,
    },
    /** Currently selected variant ID */
    selectedId: {
      type: String,
      default: null,
    },
    /** Currently hovered variant ID */
    hoveredId: {
      type: String,
      default: null,
    },
    /** Cache of distance info per variant ID */
    distanceCache: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['select', 'hover', 'unhover', 'view-details'],
  data() {
    return {
      sortBy: 'position',
      filterPathogenicity: null,
      filterDistance: null,
      // Options for selects
      sortOptions: [
        { title: 'Position', value: 'position' },
        { title: 'Distance to DNA', value: 'distance' },
        { title: 'Pathogenicity', value: 'pathogenicity' },
      ],
      pathogenicityOptions: [
        { title: 'Pathogenic', value: 'PATHOGENIC' },
        { title: 'Likely Pathogenic', value: 'LIKELY_PATHOGENIC' },
        { title: 'VUS', value: 'VUS' },
        { title: 'Likely Benign', value: 'LIKELY_BENIGN' },
        { title: 'Benign', value: 'BENIGN' },
      ],
      distanceOptions: [
        { title: 'Close (<5 A)', value: 'close' },
        { title: 'Medium (5-10 A)', value: 'medium' },
        { title: 'Far (>10 A)', value: 'far' },
      ],
    };
  },
  computed: {
    filteredAndSortedVariants() {
      let variants = [...this.variants];

      // Apply pathogenicity filter
      if (this.filterPathogenicity) {
        variants = variants.filter((v) => {
          const classification = (v.classificationVerdict || '').toUpperCase();
          if (this.filterPathogenicity === 'VUS') {
            return classification.includes('UNCERTAIN') || classification.includes('VUS');
          }
          return classification.includes(this.filterPathogenicity);
        });
      }

      // Apply distance filter
      if (this.filterDistance) {
        variants = variants.filter((v) => {
          const category = this.getVariantDistanceCategory(v);
          return category === this.filterDistance;
        });
      }

      // Apply sorting
      variants.sort((a, b) => {
        if (this.sortBy === 'position') {
          return (this.extractAAPosition(a) || 0) - (this.extractAAPosition(b) || 0);
        }
        if (this.sortBy === 'distance') {
          const distA = this.getVariantDistanceValue(a);
          const distB = this.getVariantDistanceValue(b);
          return distA - distB;
        }
        if (this.sortBy === 'pathogenicity') {
          return (
            getPathogenicityScore(b.classificationVerdict) -
            getPathogenicityScore(a.classificationVerdict)
          );
        }
        return 0;
      });

      return variants;
    },
  },
  methods: {
    extractAAPosition(variant) {
      return extractAAPositionUtil(variant);
    },

    getVariantChipColor(variant) {
      return getPathogenicityColor(variant.classificationVerdict);
    },

    getVariantLabel(variant) {
      const pNotation = extractPNotation(variant.protein);
      return pNotation || variant.simple_id || variant.variant_id;
    },

    getVariantDistanceCategory(variant) {
      const info = this.distanceCache[variant.variant_id];
      return info ? info.category : null;
    },

    getVariantDistanceValue(variant) {
      const info = this.distanceCache[variant.variant_id];
      return info ? info.distance : Infinity;
    },

    getVariantDistanceFormatted(variant) {
      const info = this.distanceCache[variant.variant_id];
      return info ? `${info.distanceFormatted} A` : null;
    },

    getDistanceChipColor(category) {
      if (category === 'close') return 'error';
      if (category === 'medium') return 'warning';
      return 'success';
    },

    clearFilters() {
      this.filterPathogenicity = null;
      this.filterDistance = null;
    },
  },
};
</script>
