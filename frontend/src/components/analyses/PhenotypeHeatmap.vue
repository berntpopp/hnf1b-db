<template>
  <div ref="root" class="phenotype-heatmap-container" v-bind="ariaProps">
    <span :id="titleId" class="sr-only">{{ chartName }}</span>
    <span :id="descId" class="sr-only">{{ description }}</span>

    <div class="heatmap-toolbar">
      <ChartExportMenu
        :svg-el="svgEl"
        :rows="exportRows"
        :columns="exportColumns"
        :chart-name="chartName"
      />
    </div>

    <div v-if="matrix.columns.length === 0" class="heatmap-empty">
      No phenotype data recorded for this variant's carriers.
    </div>

    <template v-else>
      <!-- Organ-system colour key (explicit legend, above the chart, wrapping) -->
      <ul class="heatmap-legend" aria-label="Organ-system colour key">
        <li v-for="lg in legendItems" :key="lg.key" class="heatmap-legend-item">
          <span
            class="heatmap-legend-swatch"
            :style="{ backgroundColor: lg.color }"
            aria-hidden="true"
          />
          {{ lg.label }}
        </li>
      </ul>

      <!-- WIDE (container >= 680px): D3 SVG heatmap, fills width and centres -->
      <div v-if="!isCompact" ref="chart" class="heatmap-svg-host" aria-hidden="true" />

      <!-- NARROW (container < 680px): adaptive matrix table, sticky first column -->
      <div
        v-else
        class="heatmap-compact-scroll"
        role="group"
        :aria-label="`${chartName} — data table`"
      >
        <table class="heatmap-compact-table">
          <thead>
            <tr>
              <th scope="col" class="hm-sticky hm-corner">Individual</th>
              <th v-for="c in matrix.columns" :key="c.id" scope="col" class="hm-colhead">
                <span :title="`${c.label} (${c.id})`">{{ c.label }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in matrix.rows" :key="r.phenopacketId">
              <th scope="row" class="hm-sticky hm-rowhead">
                <router-link :to="`/phenopackets/${r.phenopacketId}`">
                  {{ r.subjectId }}
                </router-link>
              </th>
              <td
                v-for="c in matrix.columns"
                :key="c.id"
                class="hm-cell"
                :title="compactCellTitle(r, c)"
              >
                <span
                  class="hm-dot"
                  :class="`hm-${matrix.cells[r.phenopacketId][c.id]}`"
                  :style="cellDotStyle(matrix.cells[r.phenopacketId][c.id], c.color)"
                  aria-hidden="true"
                />
                <span class="sr-only">{{ cellLabel(matrix.cells[r.phenopacketId][c.id]) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Shared truncation / expand toggle -->
      <div v-if="matrix.truncated || showAll" class="heatmap-truncation">
        Showing the {{ matrix.shownTerms }} most frequent of {{ matrix.totalTerms }} phenotypes.
        <button type="button" class="heatmap-expand" @click="showAll = !showAll">
          {{ showAll ? 'Show top phenotypes' : `Show all ${matrix.totalTerms}` }}
        </button>
      </div>

      <!-- Accessible full textual matrix (kept in both modes) -->
      <details class="chart-data-table">
        <summary>View data as table</summary>
        <table>
          <thead>
            <tr>
              <th>Individual</th>
              <th v-for="c in matrix.columns" :key="c.id">{{ c.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in matrix.rows" :key="r.phenopacketId">
              <td>
                <router-link :to="`/phenopackets/${r.phenopacketId}`">
                  {{ r.subjectId }}
                </router-link>
              </td>
              <td v-for="c in matrix.columns" :key="c.id">
                {{ cellLabel(matrix.cells[r.phenopacketId][c.id]) }}
              </td>
            </tr>
          </tbody>
        </table>
      </details>
    </template>
  </div>
</template>

<script>
import { ref, computed } from 'vue';
import { useTheme } from 'vuetify';
import * as d3 from 'd3';
import ChartExportMenu from '@/components/analyses/ChartExportMenu.vue';
import { useChartAccessibility } from '@/composables/useChartAccessibility';
import { buildPhenotypeMatrix } from '@/utils/phenotypeMatrix';
import { TIMELINE_COLORS } from '@/utils/ageParser';

// Container width (px) below which the SVG heatmap is replaced by an adaptive
// table. Matches Vuetify 3's `sm` lower bound; phones fall below it.
const COMPACT_BREAKPOINT = 680;
const MIN_CELL = 26; // keep cells legible / tappable
const MAX_CELL = 68; // don't let a sparse matrix blow up on wide screens
const ROW_LABEL_W = 64; // gutter for subject-id row labels
const RIGHT_PAD = 10;
const GROUP_BAND_H = 8;
const COL_FONT = 10;
const COL_LABEL_MAX = 60; // chars before ellipsis (high: keep full phenotype names)
const LABEL_ROT_DEG = 55;
const HEADER_MAX = 300; // px cap on the rotated-label header band

export default {
  name: 'PhenotypeHeatmap',
  components: { ChartExportMenu },
  props: {
    individuals: { type: Array, default: () => [] },
    chartName: { type: String, default: 'Phenotype heatmap' },
    maxTerms: { type: Number, default: 30 },
  },
  setup(props) {
    const theme = useTheme();
    const svgEl = ref(null);
    const showAll = ref(false);
    // Start wide so SSR/tests default to the heatmap path; the ResizeObserver
    // corrects this to the real container width on mount.
    const containerWidth = ref(960);

    const matrix = computed(() =>
      buildPhenotypeMatrix(props.individuals, {
        maxTerms: showAll.value ? undefined : props.maxTerms,
      })
    );

    // Export always reflects the FULL, untruncated matrix (spec §G4) — never the
    // on-screen capped/`showAll` view, so an exported figure is never silently cropped.
    const fullMatrix = computed(() => buildPhenotypeMatrix(props.individuals, {}));

    const exportColumns = computed(() => [
      { key: 'individual', label: 'Individual' },
      ...fullMatrix.value.columns.map((c) => ({ key: c.id, label: c.label })),
    ]);
    const exportRows = computed(() =>
      fullMatrix.value.rows.map((r) => {
        const row = { individual: r.subjectId };
        for (const c of fullMatrix.value.columns) {
          row[c.id] = fullMatrix.value.cells[r.phenopacketId][c.id];
        }
        return row;
      })
    );

    // De-duplicated organ-system colour key, in column order.
    const legendItems = computed(() => {
      const seen = new Map();
      for (const c of matrix.value.columns) {
        if (!seen.has(c.organSystem)) {
          seen.set(c.organSystem, { key: c.organSystem, label: c.organLabel, color: c.color });
        }
      }
      return [...seen.values()];
    });

    const isCompact = computed(() => containerWidth.value < COMPACT_BREAKPOINT);

    const summary = computed(() => {
      const m = matrix.value;
      if (!m.columns.length) return `${props.chartName}: no phenotype data.`;
      return `${props.chartName}: ${m.rows.length} individuals by ${m.shownTerms} phenotypes, colored by organ system.`;
    });

    const a11y = useChartAccessibility({ chartName: props.chartName, summary });
    const themeName = computed(() => theme.global.name.value);

    return {
      theme,
      themeName,
      svgEl,
      showAll,
      containerWidth,
      isCompact,
      matrix,
      legendItems,
      exportRows,
      exportColumns,
      ...a11y,
    };
  },
  watch: {
    individuals: {
      handler() {
        this.scheduleRender();
      },
      deep: true,
    },
    showAll() {
      this.scheduleRender();
    },
    themeName() {
      this.scheduleRender();
    },
    isCompact() {
      // Switching into/out of the table view adds/removes the chart host.
      this.scheduleRender();
    },
    containerWidth() {
      this.scheduleRender();
    },
  },
  mounted() {
    this.measure();
    if (typeof ResizeObserver !== 'undefined') {
      this.resizeObserver = new ResizeObserver(() => this.measure());
      if (this.$refs.root) this.resizeObserver.observe(this.$refs.root);
    }
    this.scheduleRender();
  },
  beforeUnmount() {
    if (this.resizeObserver) this.resizeObserver.disconnect();
  },
  methods: {
    measure() {
      const w = this.$refs.root?.clientWidth;
      // Ignore 0 (display:none / pre-layout / happy-dom) so tests keep the default.
      if (w && Math.abs(w - this.containerWidth) > 1) this.containerWidth = w;
    },
    scheduleRender() {
      this.$nextTick(() => this.renderChart());
    },
    cellLabel(status) {
      if (status === 'present') return 'Present';
      if (status === 'excluded') return 'Excluded';
      return 'Not reported';
    },
    compactCellTitle(row, col) {
      return `${row.subjectId} — ${col.label} (${col.id}): ${this.cellLabel(
        this.matrix.cells[row.phenopacketId][col.id]
      ).toLowerCase()}`;
    },
    cellDotStyle(status, color) {
      if (status === 'present') return { backgroundColor: color };
      if (status === 'excluded') {
        return {
          backgroundColor: 'transparent',
          border: '1.5px solid rgba(var(--v-theme-on-surface), 0.45)',
        };
      }
      return { backgroundColor: 'rgba(var(--v-theme-on-surface), 0.06)' };
    },
    themeColor(token, fallback) {
      const c = this.theme.current.value?.colors?.[token];
      return c || fallback;
    },
    renderChart() {
      if (this.isCompact) {
        this.svgEl = null;
        return;
      }
      const host = this.$refs.chart;
      if (!host) return;
      d3.select(host).selectAll('*').remove();
      // Tooltip lives on the (non-clipping) container so horizontal scroll of the
      // chart host never cuts it off; clear any prior instance first.
      const container = this.$refs.root;
      d3.select(container).selectAll('.heatmap-tooltip').remove();

      const m = this.matrix;
      if (!m.columns.length) return;

      const onSurface = this.themeColor('on-surface', '#1d1b20');
      const surface = this.themeColor('surface', '#ffffff');

      const nCols = m.columns.length;
      const nRows = m.rows.length;
      const availW = Math.max(280, host.clientWidth || this.containerWidth || 600);

      // Longest (capped) column label drives both the header height (vertical
      // extent of the rotated text) and the right margin (its rightward
      // overhang past the last column) — so labels are never clipped top OR right.
      const rot = (LABEL_ROT_DEG * Math.PI) / 180;
      const maxChars = Math.min(
        COL_LABEL_MAX,
        m.columns.reduce((mx, c) => Math.max(mx, c.label.length), 0)
      );
      const labelTextW = maxChars * COL_FONT * 0.6;
      const groupZoneH = GROUP_BAND_H + 14; // band + group text
      const colLabelH = Math.min(
        HEADER_MAX - groupZoneH - 10,
        Math.ceil(labelTextW * Math.sin(rot))
      );
      const headerH = colLabelH + groupZoneH + 10;
      const rightMargin = Math.max(RIGHT_PAD, Math.ceil(labelTextW * Math.cos(rot)) + 4);

      // Container-driven cell sizing: fill the available width, clamped so cells
      // stay legible (min) and a sparse matrix doesn't balloon (max).
      const rawCell = (availW - ROW_LABEL_W - rightMargin) / nCols;
      const cell = Math.max(MIN_CELL, Math.min(MAX_CELL, rawCell));
      const gridW = nCols * cell;

      const contentW = ROW_LABEL_W + gridW + rightMargin;
      const svgW = Math.max(contentW, availW); // fill the container width
      // Centre the grid horizontally when it is narrower than the container.
      const gridLeft = ROW_LABEL_W + Math.max(0, (svgW - rightMargin - ROW_LABEL_W - gridW) / 2);
      const height = headerH + nRows * cell + 16;

      const svgRoot = d3
        .select(host)
        .append('svg')
        .attr('width', svgW)
        .attr('height', height)
        .attr('viewBox', `0 0 ${svgW} ${height}`)
        .attr('preserveAspectRatio', 'xMidYMin meet')
        .attr('role', 'presentation')
        .style('max-width', '100%')
        .style('overflow', 'visible');
      this.svgEl = svgRoot.node();

      const g = svgRoot.append('g').attr('transform', `translate(${gridLeft},${headerH})`);

      const tooltip = d3
        .select(container)
        .append('div')
        .attr('class', 'heatmap-tooltip')
        .style('opacity', 0)
        .style('position', 'absolute')
        .style('background-color', surface)
        .style('color', onSurface)
        .style('border', `1px solid ${onSurface}33`)
        .style('padding', '8px')
        .style('border-radius', '5px')
        .style('pointer-events', 'none')
        .style('z-index', '1000')
        .style('font-size', '12px')
        .style('max-width', '260px')
        .style('box-shadow', '0 2px 6px rgba(0,0,0,0.25)');

      // Organ-system group bands; inline band text only when it fits its band.
      m.groups.forEach((grp) => {
        const bandW = grp.span * cell;
        g.append('rect')
          .attr('x', grp.startIndex * cell)
          .attr('y', -headerH)
          .attr('width', bandW)
          .attr('height', GROUP_BAND_H)
          .attr('fill', grp.color)
          .attr('rx', 2);
        // Approx text width; skip the label if it would overflow its band
        // (narrow single-column groups are named in the legend instead).
        if (grp.label.length * COL_FONT * 0.58 <= bandW - 4) {
          g.append('text')
            .attr('x', grp.startIndex * cell + bandW / 2)
            .attr('y', -headerH + GROUP_BAND_H + 11)
            .attr('text-anchor', 'middle')
            .attr('font-size', '10px')
            .attr('fill', onSurface)
            .text(grp.label);
        }
      });

      // Column (term) labels, rotated; anchored just above the grid.
      m.columns.forEach((col, ci) => {
        const text =
          col.label.length > COL_LABEL_MAX
            ? `${col.label.slice(0, COL_LABEL_MAX - 1)}…`
            : col.label;
        g.append('text')
          .attr('transform', `translate(${ci * cell + cell / 2}, -8) rotate(-${LABEL_ROT_DEG})`)
          .attr('text-anchor', 'start')
          .attr('font-size', `${COL_FONT}px`)
          .attr('fill', onSurface)
          .text(text)
          .append('title')
          .text(`${col.label} (${col.id})`);
      });

      // Row (individual) labels — clickable (SPA navigation).
      m.rows.forEach((row, ri) => {
        const t = g
          .append('text')
          .attr('x', -8)
          .attr('y', ri * cell + cell / 2 + 4)
          .attr('text-anchor', 'end')
          .attr('font-size', '11px')
          .attr('fill', onSurface)
          .style('cursor', 'pointer')
          .text(row.subjectId)
          .on('click', () => this.$router.push(`/phenopackets/${row.phenopacketId}`));
        t.append('title').text('View individual');
      });

      const statusFill = (status, color) => {
        if (status === 'present') return color;
        if (status === 'excluded') return TIMELINE_COLORS.excluded;
        return 'transparent';
      };

      m.rows.forEach((row, ri) => {
        m.columns.forEach((col, ci) => {
          const status = m.cells[row.phenopacketId][col.id];
          const conflict = m.conflicts.has(`${row.phenopacketId}::${col.id}`);
          const inset = Math.min(2, cell * 0.08);
          g.append('rect')
            .attr('x', ci * cell + inset)
            .attr('y', ri * cell + inset)
            .attr('width', cell - inset * 2)
            .attr('height', cell - inset * 2)
            .attr('rx', 3)
            .attr('fill', statusFill(status, col.color))
            .attr('stroke', `${onSurface}22`)
            .attr('stroke-width', status === 'not-reported' ? 0.5 : 1)
            .style('cursor', 'default')
            .on('mouseover', function () {
              d3.select(this).attr('stroke', onSurface).attr('stroke-width', 1.5);
              const label =
                status === 'present'
                  ? 'Present'
                  : status === 'excluded'
                    ? 'Excluded'
                    : 'Not reported';
              tooltip
                .html(
                  `<strong>${row.subjectId}</strong><br>${col.label} <em>(${col.id})</em><br>${col.organLabel} · ${label}` +
                    (conflict ? '<br><em>also reported excluded</em>' : '')
                )
                .transition()
                .duration(150)
                .style('opacity', 1);
            })
            .on('mousemove', (event) => {
              const rect = container.getBoundingClientRect();
              tooltip
                .style('left', `${event.clientX - rect.left + 12}px`)
                .style('top', `${event.clientY - rect.top - 10}px`);
            })
            .on('mouseleave', function () {
              d3.select(this)
                .attr('stroke', `${onSurface}22`)
                .attr('stroke-width', status === 'not-reported' ? 0.5 : 1);
              tooltip.transition().duration(150).style('opacity', 0);
            });
        });
      });
    },
  },
};
</script>

<style scoped>
.phenotype-heatmap-container {
  max-width: 100%;
  width: 100%;
  margin: auto;
  position: relative;
}
/* Positioned strip that reserves space for the absolutely-positioned export
   button (ChartExportMenu pins it top:4/right:4, ~40px tall), so the button
   never covers the legend or chart below — even on narrow screens where the
   legend fills the full width. */
.heatmap-toolbar {
  position: relative;
  min-height: 48px;
}
.heatmap-empty {
  padding: 32px;
  text-align: center;
  color: rgb(var(--v-theme-on-surface), 0.6);
}

/* Organ-system colour key */
.heatmap-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  list-style: none;
  padding: 0;
  margin: 0 0 10px;
}
.heatmap-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: rgb(var(--v-theme-on-surface), 0.78);
}
.heatmap-legend-swatch {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  flex: 0 0 auto;
}

/* Wide SVG heatmap host (scrolls only if the matrix is wider than the card) */
.heatmap-svg-host {
  width: 100%;
  overflow-x: auto;
}

/* Narrow adaptive matrix table */
.heatmap-compact-scroll {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border: 1px solid rgb(var(--v-theme-on-surface), 0.12);
  border-radius: 6px;
}
.heatmap-compact-table {
  border-collapse: separate;
  border-spacing: 0;
  font-size: 12px;
  width: max-content;
}
.heatmap-compact-table th,
.heatmap-compact-table td {
  padding: 6px 8px;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.08);
  text-align: center;
  white-space: nowrap;
}
.heatmap-compact-table .hm-colhead {
  /* Full phenotype labels — never truncated; the table scrolls horizontally. */
  font-weight: 600;
  font-size: 11px;
  color: rgb(var(--v-theme-on-surface), 0.8);
  vertical-align: bottom;
}
.hm-sticky {
  position: sticky;
  left: 0;
  z-index: 2;
  background: rgb(var(--v-theme-surface));
  text-align: left;
  box-shadow: 1px 0 0 rgb(var(--v-theme-on-surface), 0.12);
}
.hm-corner {
  z-index: 3;
}
.hm-rowhead {
  font-weight: 600;
}
.hm-rowhead a {
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
}
.hm-rowhead a:hover {
  text-decoration: underline;
}
.hm-dot {
  display: inline-block;
  width: 16px;
  height: 16px;
  border-radius: 4px;
  vertical-align: middle;
}

.heatmap-truncation {
  margin-top: 8px;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface), 0.7);
}
.heatmap-expand {
  background: none;
  border: none;
  color: rgb(var(--v-theme-primary));
  cursor: pointer;
  text-decoration: underline;
  font-size: 12px;
}
.chart-data-table {
  margin-top: 16px;
  font-size: 13px;
}
.chart-data-table summary {
  cursor: pointer;
  padding: 4px 0;
  color: rgb(var(--v-theme-on-surface), 0.7);
}
.chart-data-table table {
  border-collapse: collapse;
  margin-top: 8px;
}
.chart-data-table th,
.chart-data-table td {
  padding: 4px 8px;
  border: 1px solid rgb(var(--v-theme-on-surface), 0.12);
  text-align: left;
  white-space: nowrap;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
