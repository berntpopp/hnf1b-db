<!-- src/components/common/ColumnHeaderFilter.vue -->
<!--
  Reusable column header with inline filter button.

  Following UI/UX best practices:
  - Filter icon is inline with column header text (not separate column)
  - Compact but clickable button size (24x24px)
  - Clear visual indication when filter is active
  - Dropdown menu for filter selection
-->
<template>
  <div class="column-header-filter d-flex align-center ga-1">
    <!-- Sortable header text -->
    <span class="sortable-text d-flex align-center" @click="$emit('sort')">
      <span class="header-text">{{ title }}</span>
      <v-icon v-if="sortIcon" size="small" class="ml-1">
        {{ sortIcon }}
      </v-icon>
    </span>

    <!-- Filter button with dropdown menu -->
    <v-menu :close-on-content-click="false" location="bottom">
      <template #activator="{ props: menuProps }">
        <v-btn
          icon
          size="x-small"
          variant="text"
          v-bind="menuProps"
          :color="hasActiveFilter ? 'primary' : 'default'"
          class="filter-btn"
        >
          <v-icon size="small">
            {{ hasActiveFilter ? 'mdi-filter' : 'mdi-filter-outline' }}
          </v-icon>
        </v-btn>
      </template>

      <v-card min-width="200" max-width="280">
        <v-card-title class="text-subtitle-2 py-2 d-flex align-center">
          <v-icon size="small" class="mr-2">{{ filterIcon }}</v-icon>
          Filter: {{ title }}
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-3">
          <v-select
            :model-value="modelValue"
            :items="options"
            :label="selectLabel"
            density="compact"
            variant="outlined"
            clearable
            hide-details
            @update:model-value="$emit('update:modelValue', $event)"
          />
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-2">
          <v-spacer />
          <v-btn size="small" variant="text" @click="$emit('clear')">Clear</v-btn>
        </v-card-actions>
      </v-card>
    </v-menu>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  /** Column title text */
  title: {
    type: String,
    required: true,
  },
  /** Current filter value (v-model) */
  modelValue: {
    type: [String, Number, null],
    default: null,
  },
  /** Filter dropdown options */
  options: {
    type: Array,
    required: true,
  },
  /** Select input label */
  selectLabel: {
    type: String,
    default: 'Select value',
  },
  /** Icon for filter dropdown header */
  filterIcon: {
    type: String,
    default: 'mdi-filter-variant',
  },
  /** Sort icon (if sorted) */
  sortIcon: {
    type: String,
    default: null,
  },
});

defineEmits(['update:modelValue', 'sort', 'clear']);

const hasActiveFilter = computed(() => {
  return props.modelValue !== null && props.modelValue !== undefined && props.modelValue !== '';
});
</script>

<style scoped>
.column-header-filter {
  white-space: nowrap;
}

.sortable-text {
  cursor: pointer;
  user-select: none;
  transition: opacity 0.2s;
}

.sortable-text:hover {
  opacity: 0.7;
}

.header-text {
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: #37474f;
}

/* Properly sized filter button */
.filter-btn {
  min-width: 24px !important;
  width: 24px !important;
  height: 24px !important;
}
</style>
