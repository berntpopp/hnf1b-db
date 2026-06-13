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

  Styling follows the app's design language: a left-aligned caption column,
  the canonical primary `v-btn-toggle` (matching StructureControls), and soft
  tonal category-coloured chips (matching the original variant legend).
-->
<template>
  <div class="variant-plot-controls">
    <!-- Colour-by mode toggle -->
    <div class="vpc-row">
      <span class="vpc-label">Colour by</span>
      <v-btn-toggle
        :model-value="modelValue.coloringMode"
        mandatory
        divided
        rounded="lg"
        variant="outlined"
        color="primary"
        aria-label="Variant colouring mode"
        class="vpc-toggle"
        @update:model-value="setMode"
      >
        <v-btn value="classification" size="small" data-testid="colorby-classification">
          <v-icon start size="small">mdi-flag-variant</v-icon>
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
      class="vpc-row vpc-row--filter"
      :data-testid="`filter-row-${row.dim}`"
    >
      <span class="vpc-label">{{ row.label }}</span>
      <div class="vpc-chips">
        <span v-for="item in row.items" :key="item.key" class="filter-group">
          <v-chip
            size="small"
            :color="item.visible ? item.color : undefined"
            :variant="item.visible ? 'tonal' : 'outlined'"
            class="filter-chip"
            :class="{ 'filter-chip--hidden': !item.visible }"
            :aria-pressed="item.visible"
            :data-testid="`filter-chip-${row.dim}-${item.key}`"
            @click="onToggle(row.dim, item.key)"
          >
            <span class="filter-dot" :style="{ backgroundColor: item.color }" />
            {{ item.label }}
            <span class="filter-count">{{ item.count }}</span>
          </v-chip>
          <button
            type="button"
            class="only-btn"
            :title="`Show only ${item.label}`"
            :aria-label="`Show only ${item.label}`"
            :data-testid="`filter-only-${row.dim}-${item.key}`"
            @click="onOnly(row.dim, item.key)"
          >
            only
          </button>
        </span>
        <v-btn
          class="all-btn"
          size="x-small"
          variant="text"
          color="primary"
          :data-testid="`filter-all-${row.dim}`"
          @click="onAll(row.dim)"
        >
          All
        </v-btn>
      </div>
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
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* One row = a fixed caption column + its content (toggle or chips). */
.vpc-row {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 28px;
}

.vpc-row--filter {
  align-items: flex-start;
}

/* Caption column — aligns "Colour by", "Classification" and "Type". */
.vpc-label {
  flex: 0 0 auto;
  width: 92px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

/* Filter-row chips wrap and top-align, so nudge their label down to match. */
.vpc-row--filter .vpc-label {
  padding-top: 5px;
}

/* Give the segmented toggle a defined outline + comfortable height/padding. */
.vpc-toggle {
  height: 34px;
}

.vpc-toggle :deep(.v-btn) {
  height: 34px;
}

.vpc-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 6px;
}

.filter-group {
  display: inline-flex;
  align-items: center;
}

.filter-chip {
  cursor: pointer;
  font-weight: 500;
  transition:
    opacity 0.15s ease,
    box-shadow 0.15s ease;
}

.filter-chip:hover {
  box-shadow: 0 1px 5px rgba(0, 0, 0, 0.16);
}

.filter-chip--hidden {
  opacity: 0.45;
}

.filter-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  margin-right: 6px;
  flex: 0 0 auto;
}

.filter-count {
  margin-left: 6px;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  opacity: 0.7;
}

/* "only" — subtle, reveals on hover/focus of its chip group so the rows stay
   clean while the power-user action remains discoverable. */
.only-btn {
  border: 0;
  background: none;
  cursor: pointer;
  padding: 0 2px 0 4px;
  font-size: 0.65rem;
  line-height: 1;
  color: rgb(var(--v-theme-primary));
  opacity: 0;
  transition: opacity 0.15s ease;
}

.filter-group:hover .only-btn,
.only-btn:focus-visible {
  opacity: 0.85;
}

.only-btn:hover {
  opacity: 1;
  text-decoration: underline;
}

.all-btn {
  min-width: 0;
  padding: 0 8px;
  margin-left: 2px;
}

/* Render the toggle button labels in the app's button style (no shouty caps). */
.vpc-row :deep(.v-btn) {
  text-transform: none;
  letter-spacing: 0.01em;
}
</style>
