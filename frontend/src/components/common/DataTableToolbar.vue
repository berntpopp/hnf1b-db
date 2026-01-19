<!-- src/components/common/DataTableToolbar.vue -->
<!--
  Enhanced data table toolbar with comprehensive features

  Features:
  - Search input with debounce
  - Active filter chips with close buttons
  - Result count display
  - Column visibility settings menu
  - Actions slot for export, add button, etc.
  - Responsive: stacks on mobile

  Props:
  - searchQuery: String - Current search query (v-model compatible)
  - searchPlaceholder: String - Placeholder text for search input
  - resultCount: Number - Total result count to display
  - resultLabel: String - Label for results (e.g., "results", "variants")
  - showResultCount: Boolean - Whether to show result count chip
  - loading: Boolean - Loading state for search input
  - debounceDelay: Number - Debounce delay in ms (default: 300)
  - activeFilters: Array - Active filters to display as chips
  - columns: Array - Column definitions for visibility menu
  - showColumnSettings: Boolean - Whether to show column settings button

  Events:
  - update:searchQuery - Emitted when search query changes
  - search - Emitted after debounce delay
  - clear-search - Emitted when search is cleared
  - remove-filter - Emitted when a filter chip is closed
  - clear-all-filters - Emitted when Clear All is clicked
  - column-toggle - Emitted when column visibility is toggled
-->
<template>
  <div class="data-table-toolbar">
    <!-- Primary Row: Search + Result Count + Actions -->
    <div class="toolbar-row d-flex align-center ga-3 flex-wrap">
      <!-- Search Input -->
      <v-text-field
        :model-value="searchQuery"
        :placeholder="searchPlaceholder"
        prepend-inner-icon="mdi-magnify"
        clearable
        :loading="loading"
        hide-details
        variant="outlined"
        density="compact"
        class="search-field"
        style="max-width: 400px; min-width: 200px"
        @update:model-value="onSearchInput"
        @click:clear="onClearSearch"
        @keyup.enter="onSearchSubmit"
      />

      <v-spacer />

      <!-- Results count -->
      <v-chip v-if="showResultCount" color="teal" size="small" variant="tonal" class="result-chip">
        <v-icon start size="x-small">mdi-database</v-icon>
        {{ resultCount.toLocaleString() }} {{ resultLabel }}
      </v-chip>

      <!-- Column visibility menu (optional) -->
      <v-menu v-if="showColumnSettings && columns.length" location="bottom end">
        <template #activator="{ props }">
          <v-btn
            v-bind="props"
            icon="mdi-table-column"
            variant="text"
            size="small"
            aria-label="Column settings"
          />
        </template>
        <v-card min-width="200">
          <v-card-title class="text-subtitle-2">Visible Columns</v-card-title>
          <v-card-text class="py-0">
            <v-checkbox
              v-for="col in columns"
              :key="col.key"
              :model-value="col.visible"
              :label="col.title"
              density="compact"
              hide-details
              class="my-1"
              @update:model-value="$emit('column-toggle', col.key, $event)"
            />
          </v-card-text>
        </v-card>
      </v-menu>

      <!-- Actions slot (export, add button, etc.) -->
      <slot name="actions" />
    </div>

    <!-- Active Filters Row (if any active filters) -->
    <div v-if="hasActiveFilters" class="filter-row d-flex align-center ga-2 mt-2 flex-wrap">
      <span class="text-caption text-medium-emphasis">Active filters:</span>

      <!-- Search query chip -->
      <v-chip
        v-if="searchQuery"
        closable
        color="primary"
        size="small"
        variant="flat"
        @click:close="onClearSearch"
      >
        <v-icon start size="x-small">mdi-magnify</v-icon>
        "{{ truncateText(searchQuery, 20) }}"
      </v-chip>

      <!-- Filter chips from prop -->
      <v-chip
        v-for="filter in activeFilters"
        :key="filter.key"
        closable
        :color="filter.color || 'secondary'"
        size="small"
        variant="flat"
        @click:close="$emit('remove-filter', filter.key)"
      >
        <v-icon v-if="filter.icon" start size="x-small">{{ filter.icon }}</v-icon>
        {{ filter.label }}
      </v-chip>

      <!-- Clear all button -->
      <v-btn
        v-if="activeFilters.length > 0 || searchQuery"
        variant="text"
        size="x-small"
        color="warning"
        @click="onClearAll"
      >
        Clear All
      </v-btn>
    </div>
  </div>
</template>

<script>
import debounce from 'just-debounce-it';

export default {
  name: 'DataTableToolbar',
  props: {
    searchQuery: {
      type: String,
      default: '',
    },
    searchPlaceholder: {
      type: String,
      default: 'Search...',
    },
    resultCount: {
      type: Number,
      default: 0,
    },
    resultLabel: {
      type: String,
      default: 'results',
    },
    showResultCount: {
      type: Boolean,
      default: true,
    },
    loading: {
      type: Boolean,
      default: false,
    },
    debounceDelay: {
      type: Number,
      default: 300,
    },
    activeFilters: {
      type: Array,
      default: () => [],
    },
    columns: {
      type: Array,
      default: () => [],
    },
    showColumnSettings: {
      type: Boolean,
      default: false,
    },
  },
  emits: [
    'update:searchQuery',
    'search',
    'clear-search',
    'remove-filter',
    'clear-all-filters',
    'column-toggle',
  ],
  computed: {
    hasActiveFilters() {
      return this.searchQuery || this.activeFilters.length > 0;
    },
  },
  created() {
    this.debouncedSearch = debounce((value) => {
      this.$emit('search', value);
    }, this.debounceDelay);
  },
  methods: {
    truncateText(text, maxLength) {
      if (!text || text.length <= maxLength) return text;
      return text.substring(0, maxLength) + '...';
    },
    onSearchInput(value) {
      this.$emit('update:searchQuery', value);
      this.debouncedSearch(value);
    },
    onSearchSubmit() {
      this.$emit('search', this.searchQuery);
    },
    onClearSearch() {
      this.$emit('update:searchQuery', '');
      this.$emit('clear-search');
    },
    onClearAll() {
      this.onClearSearch();
      this.$emit('clear-all-filters');
    },
  },
};
</script>

<style scoped>
.data-table-toolbar {
  padding: 12px 16px;
  background-color: rgba(var(--v-theme-on-surface), 0.02);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.toolbar-row {
  min-height: 40px;
}

.search-field :deep(.v-field) {
  font-size: 0.9rem;
}

.search-field :deep(.v-field__input) {
  padding-top: 8px;
  padding-bottom: 8px;
  min-height: 40px;
}

.result-chip {
  font-size: 0.8125rem;
  font-weight: 500;
}

.filter-row {
  padding-top: 4px;
}

/* Responsive: Stack on mobile */
@media (max-width: 600px) {
  .search-field {
    min-width: 100% !important;
    max-width: 100% !important;
  }

  .toolbar-row {
    flex-direction: column;
    align-items: stretch !important;
    gap: 8px !important;
  }
}
</style>
