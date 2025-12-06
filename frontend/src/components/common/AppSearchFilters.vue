<!-- src/components/common/AppSearchFilters.vue -->
<!--
  Unified Search and Filter Component

  Provides consistent search/filter UI across all table views following
  UI/UX Report guidelines and COLOR_STYLE_GUIDE.md specifications.

  Features:
  - Configurable search field with optional help menu
  - Dynamic filter dropdowns
  - Active filter chips display
  - Results count indicator
  - Responsive layout
-->
<template>
  <v-card
    class="mb-4 rounded-lg"
    elevation="2"
    variant="outlined"
    style="border-color: rgba(0, 0, 0, 0.05); background: white"
  >
    <div class="d-flex align-center px-4 py-3 border-bottom">
      <div class="text-h6 font-weight-bold text-teal-darken-2">
        {{ title }}
      </div>
    </div>

    <v-card-text>
      <v-row align="center">
        <!-- Search Field -->
        <v-col cols="12" :md="searchColWidth">
          <v-text-field
            :model-value="searchQuery"
            :label="searchLabel"
            :placeholder="searchPlaceholder"
            prepend-inner-icon="mdi-magnify"
            clearable
            :loading="loading"
            hide-details
            variant="outlined"
            density="compact"
            @update:model-value="onSearchInput"
            @click:clear="onClearSearch"
            @keyup.enter="onSearchSubmit"
          >
            <!-- Optional Help Menu -->
            <template v-if="searchHelp && searchHelp.length > 0" #append-inner>
              <v-menu>
                <template #activator="{ props }">
                  <v-btn
                    icon="mdi-help-circle-outline"
                    variant="text"
                    size="small"
                    v-bind="props"
                  />
                </template>
                <v-list density="compact">
                  <v-list-item>
                    <v-list-item-title class="font-weight-bold text-caption">
                      Search Examples:
                    </v-list-item-title>
                  </v-list-item>
                  <v-list-item v-for="(help, index) in searchHelp" :key="index">
                    <v-list-item-subtitle class="text-caption">
                      {{ help }}
                    </v-list-item-subtitle>
                  </v-list-item>
                </v-list>
              </v-menu>
            </template>
          </v-text-field>
        </v-col>

        <!-- Dynamic Filter Dropdowns -->
        <v-col v-for="filter in filters" :key="filter.key" cols="12" :md="filter.colWidth || 2">
          <v-select
            :model-value="getFilterValue(filter.key)"
            :items="filter.items"
            :item-title="filter.itemTitle || 'title'"
            :item-value="filter.itemValue || 'value'"
            :label="filter.label"
            clearable
            :disabled="loading"
            hide-details
            variant="outlined"
            density="compact"
            @update:model-value="(val) => onFilterChange(filter.key, val)"
          />
        </v-col>

        <!-- Search Button (optional) -->
        <v-col v-if="showSearchButton" cols="12" md="auto">
          <v-btn color="primary" variant="tonal" :loading="loading" @click="onSearchSubmit">
            <v-icon start>mdi-magnify</v-icon>
            Search
          </v-btn>
        </v-col>
      </v-row>

      <!-- Active Filters Display -->
      <v-row v-if="hasActiveFilters" class="mt-2">
        <v-col cols="12">
          <v-chip-group>
            <!-- Search Query Chip -->
            <v-chip
              v-if="searchQuery"
              closable
              color="primary"
              size="small"
              variant="flat"
              @click:close="onClearSearch"
            >
              <v-icon start size="small">mdi-magnify</v-icon>
              Search: {{ searchQuery }}
            </v-chip>

            <!-- Filter Chips -->
            <v-chip
              v-for="filter in activeFilterChips"
              :key="filter.key"
              closable
              :color="filter.color || 'secondary'"
              size="small"
              variant="flat"
              @click:close="onClearFilter(filter.key)"
            >
              <v-icon v-if="filter.icon" start size="small">{{ filter.icon }}</v-icon>
              {{ filter.label }}: {{ filter.displayValue }}
            </v-chip>

            <!-- Clear All Button -->
            <v-chip color="error" size="small" variant="outlined" @click="onClearAll">
              <v-icon start size="small">mdi-close</v-icon>
              Clear All
            </v-chip>
          </v-chip-group>
        </v-col>
      </v-row>

      <!-- Results Count -->
      <v-row v-if="showResultCount" class="mt-1">
        <v-col cols="12">
          <div class="d-flex align-center">
            <v-chip color="info" size="small" variant="flat">
              <v-icon start size="small">mdi-filter</v-icon>
              {{ resultCount }} {{ resultLabel }}
              <span v-if="hasActiveFilters"> (filtered)</span>
            </v-chip>
            <v-spacer />
            <v-btn
              v-if="hasActiveFilters"
              variant="text"
              size="small"
              color="primary"
              @click="onClearAll"
            >
              <v-icon start>mdi-refresh</v-icon>
              Reset Filters
            </v-btn>
          </div>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue';
import debounce from 'just-debounce-it';

const props = defineProps({
  /**
   * Title for the search section (e.g., "Search Variants")
   */
  title: {
    type: String,
    default: 'Search',
  },
  /**
   * Label for the search field
   */
  searchLabel: {
    type: String,
    default: 'Search',
  },
  /**
   * Placeholder text for search field
   */
  searchPlaceholder: {
    type: String,
    default: 'Enter search term...',
  },
  /**
   * Current search query value
   */
  searchQuery: {
    type: String,
    default: '',
  },
  /**
   * Optional array of search help examples
   */
  searchHelp: {
    type: Array,
    default: () => [],
  },
  /**
   * Array of filter configurations
   * Each filter: { key, label, items, itemTitle?, itemValue?, colWidth?, icon?, color? }
   */
  filters: {
    type: Array,
    default: () => [],
  },
  /**
   * Current filter values as object { filterKey: value }
   */
  filterValues: {
    type: Object,
    default: () => ({}),
  },
  /**
   * Number of results to display
   */
  resultCount: {
    type: Number,
    default: 0,
  },
  /**
   * Label for results (e.g., "variants", "phenopackets")
   */
  resultLabel: {
    type: String,
    default: 'results',
  },
  /**
   * Whether to show results count
   */
  showResultCount: {
    type: Boolean,
    default: true,
  },
  /**
   * Whether to show explicit search button
   */
  showSearchButton: {
    type: Boolean,
    default: false,
  },
  /**
   * Loading state
   */
  loading: {
    type: Boolean,
    default: false,
  },
  /**
   * Debounce delay for search input (ms)
   */
  debounceDelay: {
    type: Number,
    default: 300,
  },
});

const emit = defineEmits([
  'update:searchQuery',
  'update:filterValues',
  'search',
  'filter-change',
  'clear-search',
  'clear-filter',
  'clear-all',
]);

// Compute search column width based on number of filters
const searchColWidth = computed(() => {
  const filterCount = props.filters.length;
  if (filterCount === 0) return 12;
  if (filterCount <= 2) return 6;
  if (filterCount <= 4) return 4;
  return 3;
});

// Check if any filters are active
const hasActiveFilters = computed(() => {
  if (props.searchQuery) return true;
  return Object.values(props.filterValues).some(
    (val) => val !== null && val !== undefined && val !== ''
  );
});

// Get active filter chips for display
const activeFilterChips = computed(() => {
  return props.filters
    .filter((filter) => {
      const value = props.filterValues[filter.key];
      return value !== null && value !== undefined && value !== '';
    })
    .map((filter) => {
      const value = props.filterValues[filter.key];
      // Get display value - handle both simple values and objects
      let displayValue = value;
      if (filter.items && Array.isArray(filter.items)) {
        const item = filter.items.find((i) => {
          if (typeof i === 'object') {
            return i[filter.itemValue || 'value'] === value;
          }
          return i === value;
        });
        if (item && typeof item === 'object') {
          displayValue = item[filter.itemTitle || 'title'] || value;
        }
      }
      return {
        key: filter.key,
        label: filter.label,
        displayValue,
        icon: filter.icon,
        color: filter.color,
      };
    });
});

// Get filter value by key
function getFilterValue(key) {
  return props.filterValues[key] ?? null;
}

// Create debounced search handler
const debouncedSearch = debounce((value) => {
  emit('search', value);
}, props.debounceDelay);

// Handle search input
function onSearchInput(value) {
  emit('update:searchQuery', value);
  debouncedSearch(value);
}

// Handle search submit (Enter key or button click)
function onSearchSubmit() {
  emit('search', props.searchQuery);
}

// Handle filter change
function onFilterChange(key, value) {
  const newFilterValues = { ...props.filterValues, [key]: value };
  emit('update:filterValues', newFilterValues);
  emit('filter-change', { key, value, allFilters: newFilterValues });
}

// Handle clear search
function onClearSearch() {
  emit('update:searchQuery', '');
  emit('clear-search');
}

// Handle clear single filter
function onClearFilter(key) {
  const newFilterValues = { ...props.filterValues, [key]: null };
  emit('update:filterValues', newFilterValues);
  emit('clear-filter', key);
}

// Handle clear all
function onClearAll() {
  emit('update:searchQuery', '');
  const clearedFilters = {};
  props.filters.forEach((filter) => {
    clearedFilters[filter.key] = null;
  });
  emit('update:filterValues', clearedFilters);
  emit('clear-all');
}
</script>

<style scoped>
.border-bottom {
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}
</style>
