<template>
  <v-menu>
    <template #activator="{ props }">
      <v-btn v-bind="props" variant="outlined" size="small" color="primary">
        <v-icon start>mdi-download</v-icon>
        Export
      </v-btn>
    </template>
    <v-list density="compact">
      <v-list-item @click="$emit('export-png')">
        <template #prepend>
          <v-icon size="small">mdi-image</v-icon>
        </template>
        <v-list-item-title>Download PNG</v-list-item-title>
      </v-list-item>
      <v-list-item v-if="showCsv" @click="$emit('export-csv')">
        <template #prepend>
          <v-icon size="small">mdi-file-delimited</v-icon>
        </template>
        <v-list-item-title>Download CSV</v-list-item-title>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script>
/**
 * ChartExportMenu - Reusable export dropdown for chart components.
 *
 * Provides a button that opens a dropdown menu with export options:
 * - Download PNG (always shown)
 * - Download CSV (conditionally shown via showCsv prop)
 *
 * @component
 * @example
 * <ChartExportMenu
 *   :show-csv="hasData"
 *   @export-png="handlePngExport"
 *   @export-csv="handleCsvExport"
 * />
 */
export default {
  name: 'ChartExportMenu',

  props: {
    /**
     * Whether to show the CSV export option.
     * Some charts (like survival curves) may not have meaningful CSV data.
     */
    showCsv: {
      type: Boolean,
      default: true,
    },
  },

  emits: [
    /**
     * Emitted when user clicks "Download PNG"
     */
    'export-png',
    /**
     * Emitted when user clicks "Download CSV"
     */
    'export-csv',
  ],
};
</script>
