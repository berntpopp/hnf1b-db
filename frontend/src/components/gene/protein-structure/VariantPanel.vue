<!-- Presentational variant list panel (all-variants mode). -->
<!-- Filter/sort selects + variant v-list + empty state. -->
<!-- Distances are resolved by the parent and attached to each variant as _distanceInfo. -->
<template>
  <div class="variant-panel">
    <div class="variant-panel-header">
      <span class="text-subtitle-2">Variants in Structure</span>
      <v-chip size="x-small" color="primary" class="ml-2">
        {{ variants.length }}
        <template v-if="variants.length !== totalInStructure"> / {{ totalInStructure }} </template>
      </v-chip>
      <v-spacer />
      <v-tooltip text="Show all listed variants in 3D" location="top">
        <template #activator="{ props: tip }">
          <v-btn
            v-bind="tip"
            icon="mdi-eye-plus-outline"
            size="x-small"
            variant="text"
            :disabled="variants.length === 0"
            aria-label="Show all listed variants in 3D"
            @click="$emit('show-all')"
          />
        </template>
      </v-tooltip>
      <v-tooltip v-if="shownVariantIds.length" text="Hide all pinned variants" location="top">
        <template #activator="{ props: tip }">
          <v-chip
            v-bind="tip"
            size="x-small"
            color="primary"
            variant="outlined"
            closable
            close-label="Hide all pinned variants in 3D"
            prepend-icon="mdi-eye"
            @click:close="$emit('clear-shown')"
          >
            {{ shownVariantIds.length }}
          </v-chip>
        </template>
      </v-tooltip>
    </div>

    <!-- Filter and Sort Controls -->
    <div class="variant-panel-controls">
      <v-text-field
        :model-value="search"
        label="Search variants"
        placeholder="p.Arg177, c.544, Var12…"
        prepend-inner-icon="mdi-magnify"
        density="compact"
        hide-details
        variant="outlined"
        clearable
        @update:model-value="$emit('update:search', $event || '')"
      />

      <!-- Sort Control -->
      <v-select
        :model-value="sortBy"
        :items="sortOptions"
        label="Sort by"
        density="compact"
        hide-details
        variant="outlined"
        class="sort-select"
        @update:model-value="$emit('update:sortBy', $event)"
      />

      <!-- Distance Filter -->
      <v-select
        :model-value="filterDistance"
        :items="distanceOptions"
        label="DNA Distance"
        density="compact"
        hide-details
        variant="outlined"
        clearable
        class="filter-select"
        @update:model-value="$emit('update:filterDistance', $event)"
      />
    </div>

    <v-list density="compact" class="variant-list">
      <v-list-item
        v-for="variant in variants"
        :key="variant.variant_id"
        :class="{
          'variant-item-active': selectedVariantId === variant.variant_id,
          'variant-item-hover': hoveredVariantId === variant.variant_id,
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
          <span>{{ classificationLabel(variant) }}</span>
          <v-chip
            v-if="getVariantDistanceCategory(variant)"
            size="x-small"
            :color="getDistanceChipColor(getVariantDistanceCategory(variant))"
            class="ml-2"
          >
            {{ getVariantDistanceFormatted(variant) }}
          </v-chip>
        </v-list-item-subtitle>
        <template #append>
          <v-btn
            :icon="isShown(variant) ? 'mdi-eye' : 'mdi-eye-off-outline'"
            :color="isShown(variant) ? 'primary' : undefined"
            size="x-small"
            density="comfortable"
            variant="text"
            :aria-pressed="isShown(variant)"
            :aria-label="`${isShown(variant) ? 'Hide' : 'Show'} ${getVariantLabel(variant)} in 3D`"
            @click.stop="$emit('toggle-shown', variant)"
          />
        </template>
      </v-list-item>
    </v-list>
    <div v-if="variants.length === 0" class="text-center py-4 text-grey">
      <v-icon size="large" color="grey-lighten-1">mdi-alert-circle-outline</v-icon>
      <div class="text-caption mt-1">
        {{
          totalInStructure === 0 ? 'No variants in structure range' : 'No variants match filters'
        }}
      </div>
      <v-btn
        v-if="totalInStructure > 0"
        size="x-small"
        variant="text"
        color="primary"
        class="mt-2"
        @click="$emit('clear-filters')"
      >
        Clear Filters
      </v-btn>
    </div>
  </div>
</template>

<script>
import { extractPNotation } from '@/utils/hgvs';
import { INTERPRETATION_STATUS_LABELS } from '@/utils/cardStyles';
import { getVariantColorByMode } from '@/utils/variantFilters';
import { extractAAPosition as extractAAPositionUtil } from '@/utils/proteinDomains';

export default {
  name: 'VariantPanel',
  props: {
    // Already filtered + sorted variants, each carrying a resolved `_distanceInfo`.
    variants: {
      type: Array,
      default: () => [],
    },
    // Total count of variants in the structure range (pre-filter), for the "n / m" chip.
    totalInStructure: {
      type: Number,
      default: 0,
    },
    selectedVariantId: {
      type: String,
      default: null,
    },
    hoveredVariantId: {
      type: String,
      default: null,
    },
    sortBy: {
      type: String,
      default: 'position',
    },
    filterDistance: {
      type: String,
      default: null,
    },
    search: {
      type: String,
      default: '',
    },
    // Variants pinned in the 3D view (independent of the single selected variant).
    shownVariantIds: {
      type: Array,
      default: () => [],
    },
    // Colour-by mode shared with the unified controls (classification | consequence).
    coloringMode: {
      type: String,
      default: 'classification',
    },
  },
  emits: [
    'select',
    'hover',
    'unhover',
    'clear-filters',
    'update:sortBy',
    'update:filterDistance',
    'update:search',
    'toggle-shown',
    'show-all',
    'clear-shown',
  ],
  data() {
    return {
      sortOptions: [
        { title: 'Position', value: 'position' },
        { title: 'Distance to DNA', value: 'distance' },
        { title: 'Pathogenicity', value: 'pathogenicity' },
      ],
      distanceOptions: [
        { title: 'Close (<5 Å)', value: 'close' },
        { title: 'Medium (5-10 Å)', value: 'medium' },
        { title: 'Far (>10 Å)', value: 'far' },
      ],
    };
  },
  methods: {
    classificationLabel(variant) {
      const verdict = variant.classificationVerdict;
      return INTERPRETATION_STATUS_LABELS[verdict] || verdict || 'Unknown';
    },

    isShown(variant) {
      return this.shownVariantIds.includes(variant.variant_id);
    },

    extractAAPosition(variant) {
      return extractAAPositionUtil(variant);
    },

    getVariantChipColor(variant) {
      // Mode-aware (classification ⇄ consequence) to match the colour-by toggle.
      return getVariantColorByMode(variant, { coloringMode: this.coloringMode });
    },

    getVariantLabel(variant) {
      const pNotation = extractPNotation(variant.protein);
      return pNotation || variant.simple_id || variant.variant_id;
    },

    getVariantDistanceCategory(variant) {
      const info = variant._distanceInfo;
      return info ? info.category : null;
    },

    getVariantDistanceFormatted(variant) {
      const info = variant._distanceInfo;
      return info ? `${info.distanceFormatted} Å` : null;
    },

    getDistanceChipColor(category) {
      if (category === 'close') return 'error';
      if (category === 'medium') return 'warning';
      return 'success';
    },
  },
};
</script>

<style scoped>
/* Variant panel styles */
.variant-panel {
  height: 500px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-left: none;
  border-radius: 0 4px 4px 0;
  background-color: rgb(var(--v-theme-surface));
  display: flex;
  flex-direction: column;
}

.variant-panel-header {
  padding: 12px;
  background-color: rgba(var(--v-theme-on-surface), 0.04);
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  display: flex;
  align-items: center;
}

.variant-panel-controls {
  padding: 8px 12px;
  background-color: rgba(var(--v-theme-on-surface), 0.04);
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sort-select,
.filter-select {
  font-size: 12px;
}

.variant-list {
  flex: 1;
  overflow-y: auto;
  background-color: transparent;
}

.variant-item-active {
  background-color: rgba(var(--v-theme-primary), 0.14) !important;
}

.variant-item-hover {
  background-color: rgba(var(--v-theme-on-surface), 0.04);
}
</style>
