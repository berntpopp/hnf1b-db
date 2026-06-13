<!--
  VariantPlotControls — shared control bar for the variant visualizations.

  Renders, for both the protein-lollipop and gene-structure plots:
    • a "Colour by" toggle (ACMG Classification ⇄ molecular-consequence Type)
    • a pathogenicity filter row (count-aware chips + per-chip "only" + "All")
    • a consequence/type filter row (same affordances)

  Filter state is owned by the parent and synced via `v-model`; this component
  is purely presentational and delegates all state derivation to
  `@/utils/variantFilters`. Categories with zero variants are never rendered,
  so each plot only shows the chips that are meaningful for its data.
-->
<template>
  <div class="variant-plot-controls">
    <!-- Colour-by mode toggle -->
    <div class="d-flex align-center flex-wrap ga-2 mb-2">
      <span class="text-caption text-medium-emphasis font-weight-medium mr-1">Colour by:</span>
      <v-btn-toggle
        :model-value="modelValue.coloringMode"
        mandatory
        density="compact"
        variant="outlined"
        divided
        color="primary"
        aria-label="Variant colouring mode"
        @update:model-value="setMode"
      >
        <v-btn value="classification" size="small" data-testid="colorby-classification">
          <v-icon start size="small">mdi-medical-bag</v-icon>
          Classification
        </v-btn>
        <v-btn value="consequence" size="small" data-testid="colorby-consequence">
          <v-icon start size="small">mdi-dna</v-icon>
          Type
        </v-btn>
      </v-btn-toggle>
    </div>

    <!-- Filter rows -->
    <div
      v-for="row in rows"
      :key="row.dim"
      class="filter-row d-flex align-center flex-wrap ga-1 mb-1"
      :data-testid="`filter-row-${row.dim}`"
    >
      <span class="filter-row-label text-caption text-medium-emphasis mr-1">{{ row.label }}</span>
      <span
        v-for="item in row.items"
        :key="item.key"
        class="filter-group d-inline-flex align-center"
      >
        <v-chip
          size="small"
          label
          :variant="item.visible ? 'flat' : 'outlined'"
          class="filter-chip"
          :class="{ 'filter-chip--hidden': !item.visible }"
          :aria-pressed="item.visible"
          :data-testid="`filter-chip-${row.dim}-${item.key}`"
          @click="onToggle(row.dim, item.key)"
        >
          <span
            class="filter-dot"
            :style="{
              backgroundColor: item.visible ? item.color : 'transparent',
              borderColor: item.color,
            }"
          />
          {{ item.label }}
          <span class="filter-count">{{ item.count }}</span>
        </v-chip>
        <v-btn
          class="only-btn"
          size="x-small"
          variant="text"
          density="compact"
          :title="`Show only ${item.label}`"
          :aria-label="`Show only ${item.label}`"
          :data-testid="`filter-only-${row.dim}-${item.key}`"
          @click="onOnly(row.dim, item.key)"
        >
          only
        </v-btn>
      </span>
      <v-btn
        class="all-btn"
        size="x-small"
        variant="tonal"
        density="compact"
        :title="`Show all ${row.label.toLowerCase()} categories`"
        :data-testid="`filter-all-${row.dim}`"
        @click="onAll(row.dim)"
      >
        All
      </v-btn>
    </div>
  </div>
</template>

<script>
import {
  buildConsequenceLegend,
  buildPathogenicityLegend,
  withAllConsequence,
  withAllPathogenicity,
  withColoringMode,
  withOnlyConsequence,
  withOnlyPathogenicity,
  withToggledConsequence,
  withToggledPathogenicity,
} from '@/utils/variantFilters';

export default {
  name: 'VariantPlotControls',
  props: {
    /** Filter state object (see createDefaultFilterState). */
    modelValue: {
      type: Object,
      required: true,
    },
    /** Variants used to derive per-category counts. */
    variants: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['update:modelValue'],
  computed: {
    rows() {
      return [
        {
          dim: 'pathogenicity',
          label: 'Classification',
          items: buildPathogenicityLegend(this.variants, this.modelValue),
        },
        {
          dim: 'consequence',
          label: 'Type',
          items: buildConsequenceLegend(this.variants, this.modelValue),
        },
      ].filter((row) => row.items.length > 0);
    },
  },
  methods: {
    setMode(mode) {
      // v-btn-toggle is mandatory, but guard against a null update.
      if (!mode) return;
      this.$emit('update:modelValue', withColoringMode(this.modelValue, mode));
    },
    onToggle(dim, key) {
      const next =
        dim === 'pathogenicity'
          ? withToggledPathogenicity(this.modelValue, key)
          : withToggledConsequence(this.modelValue, key);
      this.$emit('update:modelValue', next);
    },
    onOnly(dim, key) {
      const next =
        dim === 'pathogenicity'
          ? withOnlyPathogenicity(this.modelValue, key)
          : withOnlyConsequence(this.modelValue, key);
      this.$emit('update:modelValue', next);
    },
    onAll(dim) {
      const next =
        dim === 'pathogenicity'
          ? withAllPathogenicity(this.modelValue)
          : withAllConsequence(this.modelValue);
      this.$emit('update:modelValue', next);
    },
  },
};
</script>

<style scoped>
.variant-plot-controls {
  font-size: 0.8125rem;
}

.filter-row-label {
  min-width: 86px;
  font-weight: 600;
}

.filter-group {
  /* Keep the chip and its "only" button visually grouped. */
  margin-right: 2px;
}

.filter-chip {
  cursor: pointer;
  transition:
    opacity 0.15s ease,
    box-shadow 0.15s ease;
}

.filter-chip:hover {
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
}

.filter-chip--hidden {
  opacity: 0.5;
}

.filter-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1.5px solid;
  margin-right: 6px;
  flex: 0 0 auto;
}

.filter-count {
  margin-left: 6px;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  opacity: 0.85;
}

.only-btn {
  min-width: 0;
  padding: 0 4px;
  font-size: 0.65rem;
  letter-spacing: 0;
  opacity: 0.55;
  text-transform: lowercase;
}

.only-btn:hover {
  opacity: 1;
}

.all-btn {
  min-width: 0;
  padding: 0 8px;
  font-size: 0.7rem;
  margin-left: 4px;
}
</style>
