<template>
  <div class="phenotype-heatmap-container" v-bind="ariaProps">
    <span :id="titleId" class="sr-only">{{ chartName }}</span>
    <span :id="descId" class="sr-only">{{ description }}</span>

    <ChartExportMenu
      :svg-el="svgEl"
      :rows="exportRows"
      :columns="exportColumns"
      :chart-name="chartName"
    />

    <div v-if="matrix.columns.length === 0" class="heatmap-empty">
      No phenotype data recorded for this variant's carriers.
    </div>

    <template v-else>
      <div ref="chart" aria-hidden="true" />
      <div v-if="matrix.truncated || showAll" class="heatmap-truncation">
        Showing the {{ matrix.shownTerms }} most frequent of {{ matrix.totalTerms }} phenotypes.
        <button type="button" class="heatmap-expand" @click="showAll = !showAll">
          {{ showAll ? 'Show top phenotypes' : `Show all ${matrix.totalTerms}` }}
        </button>
      </div>

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

    const summary = computed(() => {
      const m = matrix.value;
      if (!m.columns.length) return `${props.chartName}: no phenotype data.`;
      return `${props.chartName}: ${m.rows.length} individuals by ${m.shownTerms} phenotypes, colored by organ system.`;
    });

    const a11y = useChartAccessibility({ chartName: props.chartName, summary });
    const themeName = computed(() => theme.global.name.value);

    return { theme, themeName, svgEl, showAll, matrix, exportRows, exportColumns, ...a11y };
  },
  watch: {
    individuals: {
      handler() {
        this.renderChart();
      },
      deep: true,
    },
    showAll() {
      this.renderChart();
    },
    themeName() {
      this.renderChart();
    },
  },
  mounted() {
    this.renderChart();
    window.addEventListener('resize', this.renderChart);
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.renderChart);
  },
  methods: {
    cellLabel(status) {
      if (status === 'present') return 'Present';
      if (status === 'excluded') return 'Excluded';
      return 'Not reported';
    },
    themeColor(token, fallback) {
      const c = this.theme.current.value?.colors?.[token];
      return c || fallback;
    },
    renderChart() {
      const host = this.$refs.chart;
      if (!host) return;
      d3.select(host).selectAll('*').remove();

      const m = this.matrix;
      if (!m.columns.length) return;

      const onSurface = this.themeColor('on-surface', '#1d1b20');
      const surface = this.themeColor('surface', '#ffffff');

      const cell = 26;
      const labelW = 90;
      const headerH = 150;
      const groupBandH = 8;
      const width = labelW + m.columns.length * cell + 12;
      const height = headerH + m.rows.length * cell + 24;

      const svgRoot = d3
        .select(host)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMinYMin meet');
      this.svgEl = svgRoot.node();

      const g = svgRoot.append('g').attr('transform', `translate(${labelW},${headerH})`);

      // Tooltip (theme-aware) anchored to the container.
      const tooltip = d3
        .select(host)
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
        .style('box-shadow', '0 2px 6px rgba(0,0,0,0.25)');

      // Organ-system group bands + labels (above the column labels).
      m.groups.forEach((grp) => {
        g.append('rect')
          .attr('x', grp.startIndex * cell)
          .attr('y', -headerH)
          .attr('width', grp.span * cell)
          .attr('height', groupBandH)
          .attr('fill', grp.color)
          .attr('rx', 2);
        g.append('text')
          .attr('x', grp.startIndex * cell + (grp.span * cell) / 2)
          .attr('y', -headerH + groupBandH + 11)
          .attr('text-anchor', 'middle')
          .attr('font-size', '10px')
          .attr('fill', onSurface)
          .text(grp.label);
      });

      // Column (term) labels, rotated.
      m.columns.forEach((col, ci) => {
        g.append('text')
          .attr('transform', `translate(${ci * cell + cell / 2}, ${-groupBandH - 6}) rotate(-55)`)
          .attr('text-anchor', 'start')
          .attr('font-size', '10px')
          .attr('fill', onSurface)
          .text(col.label.length > 22 ? `${col.label.slice(0, 21)}…` : col.label)
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

      // Cells.
      const statusFill = (status, color) => {
        if (status === 'present') return color;
        if (status === 'excluded') return TIMELINE_COLORS.excluded;
        return 'transparent';
      };

      m.rows.forEach((row, ri) => {
        m.columns.forEach((col, ci) => {
          const status = m.cells[row.phenopacketId][col.id];
          const conflict = m.conflicts.has(`${row.phenopacketId}::${col.id}`);
          g.append('rect')
            .attr('x', ci * cell + 2)
            .attr('y', ri * cell + 2)
            .attr('width', cell - 4)
            .attr('height', cell - 4)
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
              const rect = host.getBoundingClientRect();
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
  overflow-x: auto;
}
.heatmap-empty {
  padding: 32px;
  text-align: center;
  color: rgb(var(--v-theme-on-surface), 0.6);
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
