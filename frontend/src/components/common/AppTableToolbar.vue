<!-- src/components/common/AppTableToolbar.vue -->
<!--
  Simple, clean table toolbar with search only

  Features:
  - Prominent search input (full width available)
  - Results count badge
  - Slot for additional actions
  - Column-based filtering is done via header slots, not here
-->
<template>
  <div class="table-toolbar">
    <div class="toolbar-row d-flex align-center ga-3">
      <!-- Search Input - takes available space -->
      <v-text-field
        :model-value="searchQuery"
        :placeholder="searchPlaceholder"
        prepend-inner-icon="mdi-magnify"
        clearable
        :loading="loading"
        hide-details
        variant="outlined"
        density="compact"
        class="search-field flex-grow-1"
        style="max-width: 400px"
        @update:model-value="onSearchInput"
        @click:clear="onClearSearch"
        @keyup.enter="onSearchSubmit"
      />

      <v-spacer />

      <!-- Results count badge -->
      <v-chip v-if="showResultCount" color="teal" size="small" variant="tonal" class="result-chip">
        <v-icon start size="x-small">mdi-database</v-icon>
        {{ resultCount.toLocaleString() }} {{ resultLabel }}
      </v-chip>

      <!-- Slot for additional actions (export, toggle, etc) -->
      <slot name="actions" />
    </div>

    <!-- Active search indicator -->
    <div v-if="searchQuery" class="active-search-row d-flex align-center ga-1 mt-2">
      <span class="text-caption text-medium-emphasis">Searching:</span>
      <v-chip closable color="primary" size="small" variant="flat" @click:close="onClearSearch">
        <v-icon start size="x-small">mdi-magnify</v-icon>
        "{{ truncateText(searchQuery, 30) }}"
      </v-chip>
    </div>
  </div>
</template>

<script setup>
import debounce from 'just-debounce-it';

const props = defineProps({
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
});

const emit = defineEmits(['update:searchQuery', 'search', 'clear-search']);

function truncateText(text, maxLength) {
  if (!text || text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

const debouncedSearch = debounce((value) => {
  emit('search', value);
}, props.debounceDelay);

function onSearchInput(value) {
  emit('update:searchQuery', value);
  debouncedSearch(value);
}

function onSearchSubmit() {
  emit('search', props.searchQuery);
}

function onClearSearch() {
  emit('update:searchQuery', '');
  emit('clear-search');
}
</script>

<style scoped>
.table-toolbar {
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

.active-search-row {
  padding-top: 4px;
}
</style>
