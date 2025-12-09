<!--
  Reusable column filter component for data table headers.

  Provides a consistent filter UI pattern across all table views:
  - Filter icon in header that indicates active state
  - Dropdown menu with filter controls
  - Clear button

  @slot default - Filter controls (v-select, v-text-field, etc.)

  @example
  <ColumnFilter
    title="Sex"
    :has-value="!!filterValues.sex"
    icon="mdi-gender-male-female"
    @clear="clearFilter('sex')"
  >
    <v-select
      v-model="filterValues.sex"
      :items="sexOptions"
      density="compact"
      clearable
    />
  </ColumnFilter>
-->
<template>
  <v-menu :close-on-content-click="false" location="bottom">
    <template #activator="{ props }">
      <v-btn
        icon
        size="x-small"
        variant="text"
        v-bind="props"
        :color="hasValue ? 'primary' : 'default'"
        class="filter-btn"
        @click.stop
      >
        <v-icon size="small">
          {{ hasValue ? 'mdi-filter' : 'mdi-filter-outline' }}
        </v-icon>
      </v-btn>
    </template>
    <v-card min-width="200" max-width="280">
      <v-card-title class="text-subtitle-2 py-2 d-flex align-center">
        <v-icon v-if="icon" size="small" class="mr-2">{{ icon }}</v-icon>
        Filter: {{ title }}
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-3">
        <slot />
      </v-card-text>
      <v-divider />
      <v-card-actions class="pa-2">
        <v-spacer />
        <v-btn size="small" variant="text" @click="$emit('clear')">Clear</v-btn>
      </v-card-actions>
    </v-card>
  </v-menu>
</template>

<script>
export default {
  name: 'ColumnFilter',
  props: {
    /**
     * Title shown in filter dropdown header
     */
    title: {
      type: String,
      required: true,
    },
    /**
     * Whether the filter currently has a value set
     */
    hasValue: {
      type: Boolean,
      default: false,
    },
    /**
     * Optional icon to show in dropdown header
     */
    icon: {
      type: String,
      default: 'mdi-filter',
    },
  },
  emits: ['clear'],
};
</script>

<style scoped>
.filter-btn {
  flex-shrink: 0;
}
</style>
