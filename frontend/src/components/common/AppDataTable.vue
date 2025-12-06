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
      <div v-if="title" class="text-subtitle-1 font-weight-bold text-teal-darken-2">
        {{ title }}
      </div>
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

    <div class="table-responsive">
      <!-- Server-side pagination table -->
      <v-data-table-server
        v-if="serverSide"
        v-bind="$attrs"
        class="process-table"
        :density="density"
        hover
      >
        <!-- Pass through all slots except internal ones -->
        <template v-for="(_, name) in $slots" :key="name" #[name]="slotData">
          <slot v-if="!internalSlots.includes(name)" :name="name" v-bind="slotData || {}" />
        </template>
      </v-data-table-server>

      <!-- Client-side pagination table -->
      <v-data-table v-else v-bind="$attrs" class="process-table" :density="density" hover>
        <!-- Pass through all slots except internal ones -->
        <template v-for="(_, name) in $slots" :key="name" #[name]="slotData">
          <slot v-if="!internalSlots.includes(name)" :name="name" v-bind="slotData || {}" />
        </template>
      </v-data-table>
    </div>
  </v-card>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: '',
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
});

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
</style>
