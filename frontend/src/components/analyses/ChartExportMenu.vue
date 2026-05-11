<template>
  <v-menu offset="4">
    <template #activator="{ props: activator }">
      <v-btn
        v-bind="activator"
        :disabled="!svgEl"
        icon="mdi-download"
        size="small"
        variant="text"
        :aria-label="`Export ${chartName}`"
        class="chart-export-menu__btn"
      />
    </template>
    <v-list density="compact">
      <v-list-item @click="exportPng">
        <v-list-item-title>Export as PNG</v-list-item-title>
      </v-list-item>
      <v-list-item @click="exportCsv">
        <v-list-item-title>Export as CSV</v-list-item-title>
      </v-list-item>
      <v-list-item @click="exportSvg">
        <v-list-item-title>Export as SVG</v-list-item-title>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script setup>
import {
  exportSvgAsPng,
  exportSvgAsSvg,
  exportDataAsCsv,
  buildExportFilename,
} from '@/utils/chartExport';
import { useAnnouncer } from '@/composables/useAccessibility';

const props = defineProps({
  svgEl: { type: [Object, Function], default: null },
  rows: { type: Array, default: () => [] },
  columns: { type: Array, default: () => [] },
  chartName: { type: String, required: true },
});

const { announce } = useAnnouncer();

function resolveSvg() {
  return typeof props.svgEl === 'function' ? props.svgEl() : props.svgEl;
}

async function exportPng() {
  const svg = resolveSvg();
  if (!svg) return;
  await exportSvgAsPng(svg, { filename: buildExportFilename(props.chartName, 'png') });
  announce('Chart exported as PNG');
}

function exportCsv() {
  exportDataAsCsv(props.rows, props.columns, buildExportFilename(props.chartName, 'csv'));
  announce('Chart exported as CSV');
}

function exportSvg() {
  const svg = resolveSvg();
  if (!svg) return;
  exportSvgAsSvg(svg, buildExportFilename(props.chartName, 'svg'));
  announce('Chart exported as SVG');
}

defineExpose({ exportPng, exportCsv, exportSvg });
</script>

<style scoped>
.chart-export-menu__btn {
  position: absolute;
  top: 4px;
  right: 4px;
  z-index: 1;
}
</style>
