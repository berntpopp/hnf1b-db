<!-- src/components/common/AppDataTable.vue -->
<!--
  Unified data table wrapper component

  Features:
  - Consistent styling across all table views
  - Supports both server-side and client-side pagination
  - Integrated toolbar slot for search/filters
  - Column-based filtering support via header slots
  - Dense mode for compact display
  - Slot passthrough to v-data-table
-->
<template>
  <v-card
    class="table-wrapper rounded-lg"
    elevation="2"
    variant="outlined"
    style="border-color: rgba(0, 0, 0, 0.05); background: white"
  >
    <!-- Optional Title Bar -->
    <div
      v-if="title || $slots['title-actions']"
      class="table-title-bar d-flex align-center justify-space-between px-4 py-2"
    >
      <component
        :is="titleTag"
        v-if="title"
        class="text-subtitle-1 font-weight-bold text-teal-darken-2 ma-0"
      >
        {{ title }}
      </component>
      <div v-if="$slots['title-actions']" class="d-flex align-center ga-2">
        <slot name="title-actions" />
      </div>
    </div>

    <!-- Integrated Toolbar Slot (for AppTableToolbar or custom search UI) -->
    <div v-if="$slots.toolbar" class="table-toolbar-container">
      <slot name="toolbar" />
    </div>

    <!-- Legacy Filters Slot (deprecated, use toolbar instead) -->
    <div v-if="$slots.filters" class="px-4 py-2 bg-grey-lighten-5 border-bottom">
      <slot name="filters" />
    </div>

    <div class="table-responsive" :class="{ 'is-mobile-cards': isMobile }">
      <!-- Server-side pagination table -->
      <v-data-table-server
        v-if="serverSide"
        v-bind="$attrs"
        class="process-table"
        :density="density"
        :mobile="isMobile"
        hover
      >
        <!-- Pass through all slots except internal ones -->
        <template v-for="(_, name) in $slots" :key="name" #[name]="slotData">
          <slot v-if="!internalSlots.includes(name)" :name="name" v-bind="slotData || {}" />
        </template>
      </v-data-table-server>

      <!-- Client-side pagination table -->
      <v-data-table
        v-else
        v-bind="$attrs"
        class="process-table"
        :density="density"
        :mobile="isMobile"
        hover
      >
        <!-- Pass through all slots except internal ones -->
        <template v-for="(_, name) in $slots" :key="name" #[name]="slotData">
          <slot v-if="!internalSlots.includes(name)" :name="name" v-bind="slotData || {}" />
        </template>
      </v-data-table>
    </div>
  </v-card>
</template>

<script setup>
import { computed } from 'vue';
import { useDisplay } from 'vuetify';

const props = defineProps({
  title: {
    type: String,
    default: '',
  },
  titleTag: {
    type: String,
    default: 'h1',
  },
  serverSide: {
    type: Boolean,
    default: true,
  },
  /**
   * Table density: 'default' | 'comfortable' | 'compact'
   * Default to 'compact' for dense data display
   */
  density: {
    type: String,
    default: 'compact',
    validator: (value) => ['default', 'comfortable', 'compact'].includes(value),
  },
  /**
   * Opt out of the responsive mobile card layout (keep the grid at all sizes).
   */
  disableMobile: {
    type: Boolean,
    default: false,
  },
});

const { smAndDown } = useDisplay();

// Below `sm` the table renders as stacked cards (Vuetify mobile mode), reusing
// every existing `#item.<key>` slot. Opt out per-table via `disable-mobile`.
const isMobile = computed(() => (props.disableMobile ? false : smAndDown.value));

// Slots that are consumed by AppDataTable itself, not passed to v-data-table
const internalSlots = ['title-actions', 'toolbar', 'filters'];
</script>

<style scoped>
.table-responsive {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  width: 100%;
}

.table-title-bar {
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  min-height: 44px;
}

.table-toolbar-container {
  /* Container for the toolbar - styling handled by AppTableToolbar */
}

.border-bottom {
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

/* Dense header styling */
:deep(.v-data-table-header__content) {
  font-weight: 600 !important;
  color: #37474f;
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.03em;
}

/* Compact row styling */
:deep(.v-data-table__td) {
  padding-top: 6px !important;
  padding-bottom: 6px !important;
  font-size: 0.875rem;
}

/* Hover effect */
:deep(.v-data-table__tr:hover td) {
  background-color: rgba(var(--v-theme-primary), 0.04) !important;
}

/* Zebra striping for better row tracking */
:deep(.v-data-table__tr:nth-child(even) td) {
  background-color: rgba(var(--v-theme-on-surface), 0.02);
}

/* Keep hover on zebra rows */
:deep(.v-data-table__tr:nth-child(even):hover td) {
  background-color: rgba(var(--v-theme-primary), 0.04) !important;
}

/* Compact pagination footer */
:deep(.v-data-table-footer) {
  font-size: 0.8125rem;
  padding: 4px 8px;
  min-height: 44px;
}

:deep(.v-data-table-footer__items-per-page) {
  padding: 0 8px;
}

:deep(.v-data-table-footer__pagination) {
  margin: 0 8px;
}

/* Column header filter button styling */
:deep(.header-wrapper) {
  width: 100%;
  gap: 4px;
}

:deep(.sortable-header) {
  cursor: pointer;
  user-select: none;
  transition: opacity 0.2s;
  min-width: 0;
}

:deep(.sortable-header:hover) {
  opacity: 0.7;
}

:deep(.header-title) {
  font-weight: 600;
  font-size: 0.75rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: #37474f;
}

:deep(.sort-icon-inactive) {
  opacity: 0.3;
  transition: opacity 0.2s;
}

:deep(.sortable-header:hover .sort-icon-inactive) {
  opacity: 0.6;
}

/* Filter menu card styling */
:deep(.v-menu > .v-overlay__content) {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* ============================================================
   Mobile card layout (Vuetify `mobile` mode, < sm)
   Each row renders as a self-contained card; each cell as a
   label (td-title) + value (td-value) flex row. Existing
   #item.<key> slots render inside td-value automatically.
   ============================================================ */
.is-mobile-cards {
  overflow-x: hidden; /* never horizontal-scroll on mobile */
  background: rgb(var(--v-theme-background));
  padding: 4px 0;
}

/* The header row is redundant in mobile mode (labels come from td-title) */
.is-mobile-cards :deep(.v-data-table__thead),
.is-mobile-cards :deep(thead.v-data-table__thead) {
  display: none;
}

/* Each mobile row = a card */
.is-mobile-cards :deep(.v-data-table__tr--mobile) {
  display: block;
  margin: 8px;
  padding: 4px 4px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 12px;
  background: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

/* Each cell = label + value row with comfortable touch height. Wrap so a wide
   value (e.g. a long classification chip) drops to its own full-width line
   below the label instead of being clipped. */
.is-mobile-cards :deep(.v-data-table__td--mobile) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 4px 12px;
  min-height: 44px;
  padding: 6px 12px !important;
  border: none !important;
  background: transparent !important;
}

/* Chips inside card values wrap their text rather than clipping. */
.is-mobile-cards :deep(.v-data-table__td-value .v-chip) {
  height: auto;
  min-height: 24px;
  white-space: normal;
  flex-shrink: 0;
  max-width: 100%;
}

.is-mobile-cards :deep(.v-data-table__td-value .v-chip .v-chip__content) {
  white-space: normal;
  /* Long single-token values (e.g. UNCERTAIN_SIGNIFICANCE) have no spaces to
     break on; allow breaking anywhere so the chip wraps instead of clipping. */
  overflow-wrap: anywhere;
  word-break: break-word;
  line-height: 1.25;
}

.is-mobile-cards :deep(.v-data-table__td--mobile:not(:last-child)) {
  border-bottom: 1px solid rgba(0, 0, 0, 0.05) !important;
}

.is-mobile-cards :deep(.v-data-table__td-title) {
  font-size: 0.75rem; /* 12px label (mobile typography floor) */
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: rgba(0, 0, 0, 0.6);
  flex: 0 0 auto;
}

/* Column-filter / sort controls live in the desktop header. In mobile mode
   Vuetify renders the header slot as each card's label, which duplicates the
   filter funnel on every row (noisy + sub-44px). Suppress the interactive
   controls inside mobile labels; keep the text. Filtering on mobile is served
   by the page search field. */
.is-mobile-cards :deep(.v-data-table__td-title .v-btn),
.is-mobile-cards :deep(.v-data-table__td-title button),
.is-mobile-cards :deep(.v-data-table__td-title .sort-icon-inactive),
.is-mobile-cards :deep(.v-data-table__td-title .v-icon) {
  display: none !important;
}

.is-mobile-cards :deep(.v-data-table__td-value) {
  font-size: 0.875rem; /* 14px value */
  text-align: right;
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

/* Keep the mobile "no data" / loading rows full width and centered */
.is-mobile-cards
  :deep(.v-data-table__tr--mobile .v-data-table__td--mobile.v-data-table-rows-no-data),
.is-mobile-cards :deep(.v-data-table-rows-no-data) {
  justify-content: center;
}
</style>
