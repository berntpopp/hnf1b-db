<template>
  <v-card flat v-bind="ariaProps">
    <v-card-title class="text-h6 d-flex align-center justify-space-between">
      <div :id="titleId" class="d-flex align-center">
        <v-icon class="mr-2">mdi-chart-line</v-icon>
        Publications by Type Over Years
      </div>
      <div class="d-flex align-center">
        <v-btn-toggle v-model="chartMode" mandatory dense color="primary">
          <v-btn value="cumulative" size="small">
            <v-icon left size="small">mdi-chart-timeline-variant</v-icon>
            Cumulative
          </v-btn>
          <v-btn value="annual" size="small">
            <v-icon left size="small">mdi-chart-line</v-icon>
            Annual
          </v-btn>
        </v-btn-toggle>
        <v-menu offset="4">
          <template #activator="{ props: activator }">
            <v-btn
              v-bind="activator"
              :disabled="!chart"
              icon="mdi-download"
              size="small"
              variant="text"
              :aria-label="`Export ${chartName}`"
              class="ml-2"
            />
          </template>
          <v-list density="compact">
            <v-list-item @click="exportPng">
              <v-list-item-title>Export as PNG</v-list-item-title>
            </v-list-item>
            <v-list-item @click="exportCsv">
              <v-list-item-title>Export as CSV</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
      </div>
    </v-card-title>

    <v-card-text>
      <!-- Loading State -->
      <div v-if="loading" class="d-flex justify-center align-center" style="min-height: 400px">
        <v-progress-circular indeterminate color="primary" size="64" />
      </div>

      <!-- Error State -->
      <div
        v-else-if="error"
        class="d-flex flex-column align-center justify-center"
        style="min-height: 400px"
      >
        <v-icon size="64" color="error" class="mb-4">mdi-alert-circle</v-icon>
        <div class="text-h6 text-error mb-2">Failed to load data</div>
        <div class="text-body-2 text-grey">{{ error }}</div>
        <v-btn color="primary" class="mt-4" @click="fetchData">
          <v-icon left>mdi-refresh</v-icon>
          Retry
        </v-btn>
      </div>

      <!-- Warning when publication metadata is missing -->
      <v-alert
        v-if="missingYearsCount > 0 && !loading && !error"
        type="warning"
        variant="tonal"
        density="compact"
        class="mb-3"
      >
        {{ missingYearsCount }} publication(s) missing year data. Run
        <code>make publications-sync</code> to fetch metadata from PubMed.
      </v-alert>

      <span :id="descId" class="sr-only">{{ description }}</span>

      <!-- Chart -->
      <div
        v-if="!loading && !error && chartData.labels && chartData.labels.length > 0"
        style="height: 500px"
      >
        <canvas ref="chartCanvas" aria-hidden="true" />
      </div>

      <!-- No Data State -->
      <div
        v-if="!loading && !error && (!chartData.labels || chartData.labels.length === 0)"
        class="d-flex flex-column align-center justify-center"
        style="min-height: 400px"
      >
        <v-icon size="64" color="grey-lighten-1" class="mb-4">mdi-chart-line</v-icon>
        <div class="text-h6 text-grey mb-2">No data available</div>
        <div v-if="missingYearsCount > 0" class="text-body-2 text-grey">
          Publication metadata not synced. Run <code>make publications-sync</code> first.
        </div>
      </div>

      <details
        v-if="!loading && !error && chartData.labels && chartData.labels.length > 0"
        class="chart-data-table"
      >
        <summary>View data as table</summary>
        <table>
          <thead>
            <tr>
              <th>Year</th>
              <th v-for="ds in chartData.datasets" :key="ds.label">{{ ds.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(year, i) in chartData.labels" :key="year">
              <td>{{ year }}</td>
              <td v-for="ds in chartData.datasets" :key="ds.label">{{ ds.data[i] }}</td>
            </tr>
          </tbody>
        </table>
      </details>
    </v-card-text>
  </v-card>
</template>

<script>
import { Chart, registerables } from 'chart.js';
import { ref, computed } from 'vue';
import { saveAs } from 'file-saver';
import { exportDataAsCsv, buildExportFilename } from '@/utils/chartExport';
import { useChartAccessibility } from '@/composables/useChartAccessibility';
import { useAnnouncer } from '@/composables/useAccessibility';
import * as API from '@/api';

// Register Chart.js components
Chart.register(...registerables);

export default {
  name: 'PublicationsTimelineChart',
  props: {
    mode: {
      type: String,
      default: 'cumulative',
      validator: (value) => ['annual', 'cumulative'].includes(value),
    },
    chartName: { type: String, default: 'Publications per year by type' },
  },
  emits: ['update:mode'],
  setup(props) {
    const titleElId = 'publications-timeline-title';
    // Source summary off a manually-bridged ref that the Options API updates in
    // processChartData below.
    const summarySource = ref('No publications data loaded yet.');
    const summary = computed(() => summarySource.value);
    const a11y = useChartAccessibility({ chartName: props.chartName, summary });
    const { announce } = useAnnouncer();
    return { ...a11y, summarySource, announce, titleElId };
  },
  data() {
    return {
      loading: false,
      error: null,
      chartData: {
        labels: [],
        datasets: [],
      },
      rawPublications: [], // Store raw data for mode switching
      chart: null,
      missingYearsCount: 0, // Track publications without year data
    };
  },
  computed: {
    chartMode: {
      get() {
        return this.mode;
      },
      set(value) {
        this.$emit('update:mode', value);
      },
    },
  },
  watch: {
    mode() {
      // Re-process and render chart when mode changes
      if (this.rawPublications.length > 0) {
        this.processChartData(this.rawPublications);
        this.$nextTick(() => {
          this.renderChart();
        });
      }
    },
  },
  mounted() {
    window.logService.debug('PublicationsTimelineChart mounted, fetching data');
    this.fetchData();
  },
  beforeUnmount() {
    if (this.chart) {
      this.chart.destroy();
    }
  },
  methods: {
    async fetchData() {
      this.loading = true;
      this.error = null;

      try {
        window.logService.debug('Fetching publications data from API');

        // Fetch publications data with year from database cache
        // (No need to query PubMed - years come from publication_metadata table)
        const response = await API.getPublicationsByType();
        const publications = response.data;

        window.logService.debug('Publications by type data received', {
          count: publications.length,
        });

        // Track how many publications have year data
        const withYears = publications.filter((p) => p.year);
        this.missingYearsCount = publications.length - withYears.length;

        if (this.missingYearsCount > 0) {
          window.logService.warn('Some publications missing year data', {
            total: publications.length,
            withYears: withYears.length,
            missing: this.missingYearsCount,
            hint: 'Run `make publications-sync` to fetch missing metadata from PubMed',
          });
        }

        // Store raw data for mode switching
        this.rawPublications = publications;

        // Process data for chart
        this.processChartData(publications);

        window.logService.debug('Chart data processed, rendering chart');

        // Render chart
        this.$nextTick(() => {
          this.renderChart();
          window.logService.info('Publications timeline chart rendered successfully');
        });
      } catch (err) {
        window.logService.error('Error fetching publications by type', {
          error: err.message,
        });
        this.error = err.message || 'An error occurred while fetching data';
      } finally {
        this.loading = false;
      }
    },

    processChartData(publications) {
      // Filter out publications without years
      const pubsWithYears = publications.filter((p) => p.year);

      if (pubsWithYears.length === 0) {
        this.chartData = { labels: [], datasets: [] };
        return;
      }

      // Group by year and type
      const yearTypeMap = {};
      const publicationTypes = new Set();

      pubsWithYears.forEach((pub) => {
        const year = pub.year;
        const type = pub.publication_type;
        const count = pub.phenopacket_count;

        if (!yearTypeMap[year]) {
          yearTypeMap[year] = {};
        }

        yearTypeMap[year][type] = (yearTypeMap[year][type] || 0) + count;
        publicationTypes.add(type);
      });

      // Sort years
      const years = Object.keys(yearTypeMap)
        .map(Number)
        .sort((a, b) => a - b);

      // Create datasets for each publication type
      const typeColors = {
        case_report: '#2196F3', // Blue
        case_series: '#4CAF50', // Green
        research: '#FF9800', // Orange
        review: '#9C27B0', // Purple
        review_and_cases: '#F44336', // Red
        screening_multiple: '#00BCD4', // Cyan
        unknown: '#757575', // Grey
      };

      const datasets = Array.from(publicationTypes).map((type) => {
        let data;

        if (this.chartMode === 'cumulative') {
          // Calculate cumulative totals
          let cumulative = 0;
          data = years.map((year) => {
            cumulative += yearTypeMap[year][type] || 0;
            return cumulative;
          });
        } else {
          // Annual data (default)
          data = years.map((year) => yearTypeMap[year][type] || 0);
        }

        return {
          label: type.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
          data: data,
          borderColor: typeColors[type] || '#757575',
          backgroundColor: typeColors[type] || '#757575',
          borderWidth: 2,
          fill: false, // Don't fill - keep all lines visible
          tension: 0.1,
        };
      });

      this.chartData = {
        labels: years,
        datasets: datasets,
      };

      // Update summary for screen readers
      if (years.length === 0) {
        this.summarySource = `${this.chartName}: no data.`;
      } else {
        const totalCount = datasets.reduce(
          (sum, ds) => sum + ds.data.reduce((s, v) => s + v, 0),
          0
        );
        const typeList = datasets.map((d) => d.label).join(', ');
        const cumulativeNote = this.chartMode === 'cumulative' ? ' (cumulative)' : ' (annual)';
        this.summarySource =
          `${this.chartName}${cumulativeNote}, ${years[0]}–${years[years.length - 1]}. ` +
          `${datasets.length} publication types: ${typeList}. ` +
          `Total ${totalCount} phenopackets.`;
      }
    },

    renderChart() {
      if (!this.$refs.chartCanvas) return;

      // Destroy existing chart
      if (this.chart) {
        this.chart.destroy();
      }

      const ctx = this.$refs.chartCanvas.getContext('2d');

      this.chart = new Chart(ctx, {
        type: 'line',
        data: this.chartData,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            title: {
              display: true,
              text:
                this.chartMode === 'cumulative'
                  ? 'Cumulative Phenopackets by Publication Type Over Years'
                  : 'Number of Phenopackets by Publication Type Over Years',
              font: {
                size: 16,
              },
            },
            legend: {
              display: true,
              position: 'top',
            },
            tooltip: {
              mode: 'index',
              intersect: false,
            },
          },
          scales: {
            x: {
              title: {
                display: true,
                text: 'Year',
                font: {
                  size: 14,
                },
              },
            },
            y: {
              title: {
                display: true,
                text:
                  this.chartMode === 'cumulative'
                    ? 'Cumulative Phenopackets'
                    : 'Number of Phenopackets',
                font: {
                  size: 14,
                },
              },
              beginAtZero: true,
              ticks: {
                precision: 0,
              },
              stacked: false, // Don't stack in cumulative mode (lines show individual totals)
            },
          },
          interaction: {
            mode: 'nearest',
            axis: 'x',
            intersect: false,
          },
        },
      });
    },

    /**
     * Build the rows + columns used by CSV export and the data-table fallback.
     * Returns { rows, columns } shaped for exportDataAsCsv.
     */
    buildExportData() {
      const columns = [
        { key: 'year', label: 'Year' },
        ...this.chartData.datasets.map((d) => ({ key: d.label, label: d.label })),
      ];
      const rows = (this.chartData.labels || []).map((year, idx) => {
        const row = { year };
        for (const ds of this.chartData.datasets) {
          row[ds.label] = ds.data[idx];
        }
        return row;
      });
      return { rows, columns };
    },

    exportPng() {
      if (!this.chart) return;
      const dataUrl = this.chart.toBase64Image('image/png', 1.0);
      // Convert data URL to Blob without fetch (fetch on a data URL works in
      // browsers but adds a microtask; do it inline so we can call saveAs sync).
      const [meta, base64] = dataUrl.split(',');
      const mime = meta.match(/data:(.*?);/)[1];
      const binary = atob(base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const blob = new Blob([bytes], { type: mime });
      saveAs(blob, buildExportFilename(this.chartName, 'png'));
      this.announce('Chart exported as PNG');
    },

    exportCsv() {
      const { rows, columns } = this.buildExportData();
      exportDataAsCsv(rows, columns, buildExportFilename(this.chartName, 'csv'));
      this.announce('Chart exported as CSV');
    },
  },
};
</script>

<style scoped>
canvas {
  max-height: 500px;
}

.chart-data-table {
  margin-top: 16px;
  font-size: 14px;
}
.chart-data-table summary {
  cursor: pointer;
  padding: 4px 0;
  color: rgb(var(--v-theme-on-surface), 0.7);
}
.chart-data-table table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
}
.chart-data-table th,
.chart-data-table td {
  padding: 4px 8px;
  border: 1px solid rgb(var(--v-theme-on-surface), 0.12);
  text-align: left;
}
</style>
