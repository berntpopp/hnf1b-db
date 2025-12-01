<!-- DNA Distance vs Pathogenicity Analysis Component -->
<template>
  <v-container fluid>
    <!-- Loading state -->
    <v-row v-if="loading" class="pa-3">
      <v-col cols="12" class="text-center">
        <v-progress-circular indeterminate color="primary" size="64" />
        <p class="mt-4">Loading 3D structure and calculating distances...</p>
        <p class="text-caption text-grey">This may take a few seconds</p>
      </v-col>
    </v-row>

    <!-- Error state -->
    <v-row v-else-if="error" class="pa-3">
      <v-col cols="12">
        <v-alert type="error" variant="tonal">
          {{ error }}
        </v-alert>
      </v-col>
    </v-row>

    <!-- Main content -->
    <template v-else>
      <!-- Summary Statistics Cards -->
      <v-row class="pa-3">
        <v-col cols="12" sm="6" md="3">
          <v-card variant="outlined" class="stat-card">
            <v-card-text class="text-center">
              <v-icon color="info" size="32"> mdi-molecule </v-icon>
              <div class="text-h5 mt-2">{{ totalVariantsInStructure }}</div>
              <div class="text-caption text-grey">Variants in Structure</div>
              <div class="text-caption text-grey-darken-1">(residues 90-186, 231-308)</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-card variant="outlined" class="stat-card">
            <v-card-text class="text-center">
              <v-icon color="error" size="32"> mdi-alert-circle </v-icon>
              <div v-if="pathogenicStats" class="text-h5 mt-2">
                {{ pathogenicStats.median.toFixed(1) }} &Aring;
              </div>
              <div class="text-caption text-grey">P/LP Median Distance</div>
              <div class="text-caption text-grey-darken-1">
                (n={{ pathogenicStats?.count || 0 }})
              </div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-card variant="outlined" class="stat-card">
            <v-card-text class="text-center">
              <v-icon color="warning" size="32"> mdi-help-circle </v-icon>
              <div v-if="vusStats" class="text-h5 mt-2">
                {{ vusStats.median.toFixed(1) }} &Aring;
              </div>
              <div class="text-caption text-grey">VUS Median Distance</div>
              <div class="text-caption text-grey-darken-1">(n={{ vusStats?.count || 0 }})</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-card variant="outlined" class="stat-card">
            <v-card-text class="text-center">
              <v-icon :color="pValueSignificant ? 'success' : 'grey'" size="32">
                {{ pValueSignificant ? 'mdi-check-circle' : 'mdi-minus-circle' }}
              </v-icon>
              <div class="text-h5 mt-2">
                {{ mannWhitneyResult ? formatPValue(mannWhitneyResult.pValue) : 'N/A' }}
              </div>
              <div class="text-caption text-grey">Mann-Whitney p-value</div>
              <div class="text-caption" :class="pValueSignificant ? 'text-success' : 'text-grey'">
                {{ pValueSignificant ? 'Significant (p < 0.05)' : 'Not significant' }}
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Visualization Row -->
      <v-row class="pa-3">
        <!-- Box Plot / Violin Plot -->
        <v-col cols="12" md="7">
          <v-card variant="outlined">
            <v-card-title class="text-subtitle-1 py-2 bg-blue-lighten-5">
              <v-icon left color="primary" size="small"> mdi-chart-box </v-icon>
              Distance Distribution by Pathogenicity
            </v-card-title>
            <v-card-text>
              <div ref="boxPlotContainer" class="chart-container" />
            </v-card-text>
          </v-card>
        </v-col>

        <!-- Distance Category Breakdown -->
        <v-col cols="12" md="5">
          <v-card variant="outlined" class="h-100">
            <v-card-title class="text-subtitle-1 py-2 bg-orange-lighten-5">
              <v-icon left color="orange" size="small"> mdi-chart-donut </v-icon>
              Distance Categories by Group
            </v-card-title>
            <v-card-text>
              <!-- P/LP Distribution -->
              <div class="mb-4">
                <div class="text-body-2 font-weight-medium mb-1">
                  Pathogenic / Likely Pathogenic
                </div>
                <div class="distance-distribution">
                  <div
                    v-for="cat in ['close', 'medium', 'far']"
                    :key="'plp-' + cat"
                    class="distance-bar"
                    :class="cat"
                    :style="{ width: getCategoryWidth('pathogenic', cat) + '%' }"
                    :title="`${getCategoryLabel(cat)}: ${pathogenicCategories[cat] || 0} variants`"
                  >
                    <span v-if="pathogenicCategories[cat] > 0">
                      {{ pathogenicCategories[cat] }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- VUS Distribution -->
              <div class="mb-4">
                <div class="text-body-2 font-weight-medium mb-1">
                  Variants of Uncertain Significance
                </div>
                <div class="distance-distribution">
                  <div
                    v-for="cat in ['close', 'medium', 'far']"
                    :key="'vus-' + cat"
                    class="distance-bar"
                    :class="cat"
                    :style="{ width: getCategoryWidth('vus', cat) + '%' }"
                    :title="`${getCategoryLabel(cat)}: ${vusCategories[cat] || 0} variants`"
                  >
                    <span v-if="vusCategories[cat] > 0">
                      {{ vusCategories[cat] }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- Legend -->
              <div class="d-flex justify-space-around text-caption text-grey mt-3">
                <span><span class="legend-dot close" /> Close (&lt;5&Aring;)</span>
                <span><span class="legend-dot medium" /> Medium (5-10&Aring;)</span>
                <span><span class="legend-dot far" /> Far (&ge;10&Aring;)</span>
              </div>

              <!-- Interpretation -->
              <v-alert
                v-if="pathogenicStats && vusStats"
                type="info"
                variant="tonal"
                density="compact"
                class="mt-4"
              >
                <div class="text-body-2">
                  <strong>Interpretation:</strong>
                  Pathogenic/Likely Pathogenic variants have a median distance of
                  <strong>{{ pathogenicStats.median.toFixed(1) }} &Aring;</strong>
                  to DNA, while VUS have a median of
                  <strong>{{ vusStats.median.toFixed(1) }} &Aring;</strong>.
                  <span v-if="pValueSignificant">
                    This difference is statistically significant (p =
                    {{ formatPValue(mannWhitneyResult?.pValue) }}), suggesting that proximity to DNA
                    may correlate with pathogenicity.
                  </span>
                  <span v-else>
                    This difference is not statistically significant at p &lt; 0.05.
                  </span>
                </div>
              </v-alert>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Statistical Details Panel -->
      <v-row class="pa-3">
        <v-col cols="12">
          <v-expansion-panels>
            <v-expansion-panel>
              <v-expansion-panel-title>
                <v-icon class="mr-2"> mdi-chart-bell-curve </v-icon>
                Statistical Analysis Details
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <v-row>
                  <v-col cols="12" md="6">
                    <h4 class="text-subtitle-1 font-weight-bold mb-2">
                      Pathogenic / Likely Pathogenic
                    </h4>
                    <v-table v-if="pathogenicStats" density="compact">
                      <tbody>
                        <tr>
                          <td>Sample Size</td>
                          <td class="text-right">{{ pathogenicStats.count }}</td>
                        </tr>
                        <tr>
                          <td>Mean</td>
                          <td class="text-right">{{ pathogenicStats.mean.toFixed(2) }} &Aring;</td>
                        </tr>
                        <tr>
                          <td>Median</td>
                          <td class="text-right">
                            {{ pathogenicStats.median.toFixed(2) }} &Aring;
                          </td>
                        </tr>
                        <tr>
                          <td>Std. Deviation</td>
                          <td class="text-right">
                            {{ pathogenicStats.stdDev.toFixed(2) }} &Aring;
                          </td>
                        </tr>
                        <tr>
                          <td>Min - Max</td>
                          <td class="text-right">
                            {{ pathogenicStats.min.toFixed(1) }} -
                            {{ pathogenicStats.max.toFixed(1) }} &Aring;
                          </td>
                        </tr>
                        <tr>
                          <td>IQR (Q1 - Q3)</td>
                          <td class="text-right">
                            {{ pathogenicStats.q1.toFixed(1) }} -
                            {{ pathogenicStats.q3.toFixed(1) }} &Aring;
                          </td>
                        </tr>
                      </tbody>
                    </v-table>
                  </v-col>
                  <v-col cols="12" md="6">
                    <h4 class="text-subtitle-1 font-weight-bold mb-2">
                      Variants of Uncertain Significance
                    </h4>
                    <v-table v-if="vusStats" density="compact">
                      <tbody>
                        <tr>
                          <td>Sample Size</td>
                          <td class="text-right">{{ vusStats.count }}</td>
                        </tr>
                        <tr>
                          <td>Mean</td>
                          <td class="text-right">{{ vusStats.mean.toFixed(2) }} &Aring;</td>
                        </tr>
                        <tr>
                          <td>Median</td>
                          <td class="text-right">{{ vusStats.median.toFixed(2) }} &Aring;</td>
                        </tr>
                        <tr>
                          <td>Std. Deviation</td>
                          <td class="text-right">{{ vusStats.stdDev.toFixed(2) }} &Aring;</td>
                        </tr>
                        <tr>
                          <td>Min - Max</td>
                          <td class="text-right">
                            {{ vusStats.min.toFixed(1) }} - {{ vusStats.max.toFixed(1) }} &Aring;
                          </td>
                        </tr>
                        <tr>
                          <td>IQR (Q1 - Q3)</td>
                          <td class="text-right">
                            {{ vusStats.q1.toFixed(1) }} - {{ vusStats.q3.toFixed(1) }} &Aring;
                          </td>
                        </tr>
                      </tbody>
                    </v-table>
                  </v-col>
                </v-row>

                <!-- Effect Size -->
                <v-row v-if="mannWhitneyResult" class="mt-4">
                  <v-col cols="12">
                    <h4 class="text-subtitle-1 font-weight-bold mb-2">Effect Size</h4>
                    <v-table density="compact">
                      <tbody>
                        <tr>
                          <td>Median Difference</td>
                          <td class="text-right">
                            {{ (pathogenicStats.median - vusStats.median).toFixed(2) }}
                            &Aring;
                          </td>
                        </tr>
                        <tr>
                          <td>Cohen's d</td>
                          <td class="text-right">
                            {{ mannWhitneyResult.cohensD.toFixed(3) }}
                            <v-chip
                              size="x-small"
                              :color="getEffectSizeColor(mannWhitneyResult.cohensD)"
                              class="ml-2"
                            >
                              {{ getEffectSizeLabel(mannWhitneyResult.cohensD) }}
                            </v-chip>
                          </td>
                        </tr>
                        <tr>
                          <td>Rank-Biserial Correlation</td>
                          <td class="text-right">
                            {{ mannWhitneyResult.rankBiserial.toFixed(3) }}
                          </td>
                        </tr>
                      </tbody>
                    </v-table>
                  </v-col>
                </v-row>

                <!-- Methodology -->
                <v-row class="mt-4">
                  <v-col cols="12">
                    <h4 class="text-subtitle-1 font-weight-bold mb-2">Methodology</h4>
                    <v-list density="compact" class="bg-transparent">
                      <v-list-item>
                        <template #prepend>
                          <v-icon size="small" color="primary">mdi-cube-outline</v-icon>
                        </template>
                        <v-list-item-title class="text-body-2">Structure</v-list-item-title>
                        <v-list-item-subtitle class="text-wrap">
                          PDB 2H8R - HNF1B DNA-binding domain (UniProt P35680 residues 90-186 and
                          231-308; linker region 187-230 not resolved)
                        </v-list-item-subtitle>
                      </v-list-item>
                      <v-list-item>
                        <template #prepend>
                          <v-icon size="small" color="primary">mdi-ruler</v-icon>
                        </template>
                        <v-list-item-title class="text-body-2">
                          Distance Calculation
                        </v-list-item-title>
                        <v-list-item-subtitle class="text-wrap">
                          Minimum Euclidean distance from any atom in the variant residue to any DNA
                          atom (closest-atom method)
                        </v-list-item-subtitle>
                      </v-list-item>
                      <v-list-item>
                        <template #prepend>
                          <v-icon size="small" color="primary">mdi-chart-bell-curve</v-icon>
                        </template>
                        <v-list-item-title class="text-body-2">Statistical Test</v-list-item-title>
                        <v-list-item-subtitle class="text-wrap">
                          Mann-Whitney U test (non-parametric, suitable for non-normal
                          distributions)
                        </v-list-item-subtitle>
                      </v-list-item>
                    </v-list>
                  </v-col>
                </v-row>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-col>
      </v-row>
    </template>
  </v-container>
</template>

<script>
import * as NGL from 'ngl';
import * as d3 from 'd3';
import { markRaw } from 'vue';
import { getVariants } from '@/api';
import { extractPNotation } from '@/utils/hgvs';
import {
  DNADistanceCalculator,
  STRUCTURE_START,
  STRUCTURE_END,
} from '@/utils/dnaDistanceCalculator';

// Store NGL objects outside Vue's reactivity system
let nglStage = null;
let nglStructureComponent = null;
let distanceCalculator = null;

export default {
  name: 'DNADistanceAnalysis',
  props: {
    width: {
      type: Number,
      default: 800,
    },
    height: {
      type: Number,
      default: 400,
    },
  },
  data() {
    return {
      loading: true,
      error: null,
      variants: [],
      variantDistances: [],
      pathogenicDistances: [],
      vusDistances: [],
      pathogenicStats: null,
      vusStats: null,
      pathogenicCategories: { close: 0, medium: 0, far: 0 },
      vusCategories: { close: 0, medium: 0, far: 0 },
      mannWhitneyResult: null,
      totalVariantsInStructure: 0,
    };
  },
  computed: {
    pValueSignificant() {
      return this.mannWhitneyResult && this.mannWhitneyResult.pValue < 0.05;
    },
  },
  mounted() {
    this.loadData();
  },
  beforeUnmount() {
    // Clean up NGL stage
    if (nglStage) {
      nglStage.dispose();
      nglStage = null;
      nglStructureComponent = null;
      distanceCalculator = null;
    }
    // Clean up tooltip
    d3.select('body').select('.dna-distance-tooltip').remove();
  },
  methods: {
    async loadData() {
      try {
        this.loading = true;
        this.error = null;

        // 1. Load variants from API
        const response = await getVariants({ page: 1, page_size: 1000 });
        this.variants = response.data || [];

        // 2. Initialize NGL and load structure (hidden, just for calculation)
        await this.initializeNGL();

        // 3. Calculate distances
        this.calculateDistances();

        // 4. Perform statistical analysis
        this.performStatisticalAnalysis();

        // 5. Render visualization - use setTimeout to ensure DOM is fully rendered
        this.loading = false;
        await this.$nextTick();
        // Additional delay to ensure container has proper dimensions
        setTimeout(() => {
          this.renderBoxPlot();
        }, 100);

        window.logService.info('DNA distance analysis complete', {
          totalVariants: this.variants.length,
          inStructure: this.totalVariantsInStructure,
          pathogenicCount: this.pathogenicDistances.length,
          vusCount: this.vusDistances.length,
        });
      } catch (err) {
        window.logService.error('Failed to load DNA distance analysis', { error: err.message });
        this.error = `Failed to load analysis: ${err.message}`;
        this.loading = false;
      }
    },

    async initializeNGL() {
      // Create a hidden container for NGL
      const container = document.createElement('div');
      container.style.width = '1px';
      container.style.height = '1px';
      container.style.position = 'absolute';
      container.style.left = '-9999px';
      document.body.appendChild(container);

      nglStage = markRaw(
        new NGL.Stage(container, {
          backgroundColor: 'white',
        })
      );

      // Load PDB structure
      nglStructureComponent = markRaw(
        await nglStage.loadFile('https://www.ebi.ac.uk/pdbe/entry-files/2h8r.cif', {
          defaultRepresentation: false,
          ext: 'cif',
        })
      );

      // Initialize distance calculator
      distanceCalculator = new DNADistanceCalculator();
      distanceCalculator.initialize(nglStructureComponent);
    },

    calculateDistances() {
      const variantsWithDistances = [];

      for (const variant of this.variants) {
        const aaPosition = this.extractAAPosition(variant);
        if (!aaPosition || aaPosition < STRUCTURE_START || aaPosition > STRUCTURE_END) {
          continue;
        }

        const distanceInfo = distanceCalculator.calculateResidueToHelixDistance(aaPosition, true);
        if (!distanceInfo) continue;

        variantsWithDistances.push({
          ...variant,
          aaPosition,
          distance: distanceInfo.distance,
          category: distanceInfo.category,
        });
      }

      this.variantDistances = variantsWithDistances;
      this.totalVariantsInStructure = variantsWithDistances.length;

      // Separate by pathogenicity
      this.pathogenicDistances = variantsWithDistances.filter((v) => {
        const cls = v.classificationVerdict?.toUpperCase() || '';
        return (
          cls.includes('PATHOGENIC') &&
          !cls.includes('LIKELY_BENIGN') &&
          !cls.includes('LIKELY BENIGN')
        );
      });

      this.vusDistances = variantsWithDistances.filter((v) => {
        const cls = v.classificationVerdict?.toUpperCase() || '';
        return cls.includes('UNCERTAIN') || cls.includes('VUS');
      });

      // Count categories
      this.pathogenicCategories = { close: 0, medium: 0, far: 0 };
      this.vusCategories = { close: 0, medium: 0, far: 0 };

      for (const v of this.pathogenicDistances) {
        this.pathogenicCategories[v.category]++;
      }
      for (const v of this.vusDistances) {
        this.vusCategories[v.category]++;
      }
    },

    performStatisticalAnalysis() {
      // Calculate statistics for each group
      this.pathogenicStats = this.calculateGroupStats(this.pathogenicDistances);
      this.vusStats = this.calculateGroupStats(this.vusDistances);

      // Perform Mann-Whitney U test
      if (this.pathogenicDistances.length >= 3 && this.vusDistances.length >= 3) {
        this.mannWhitneyResult = this.mannWhitneyU(
          this.pathogenicDistances.map((v) => v.distance),
          this.vusDistances.map((v) => v.distance)
        );
      }
    },

    calculateGroupStats(variants) {
      if (variants.length === 0) return null;

      const distances = variants.map((v) => v.distance).sort((a, b) => a - b);
      const n = distances.length;

      const sum = distances.reduce((a, b) => a + b, 0);
      const mean = sum / n;

      const mid = Math.floor(n / 2);
      const median = n % 2 !== 0 ? distances[mid] : (distances[mid - 1] + distances[mid]) / 2;

      const squaredDiffs = distances.map((v) => Math.pow(v - mean, 2));
      const avgSquaredDiff = squaredDiffs.reduce((a, b) => a + b, 0) / n;
      const stdDev = Math.sqrt(avgSquaredDiff);

      const q1Index = Math.floor(n * 0.25);
      const q3Index = Math.floor(n * 0.75);

      return {
        count: n,
        mean,
        median,
        stdDev,
        min: distances[0],
        max: distances[n - 1],
        q1: distances[q1Index],
        q3: distances[q3Index],
        distances,
      };
    },

    mannWhitneyU(x, y) {
      // Combine and rank
      const combined = [
        ...x.map((v) => ({ value: v, group: 'x' })),
        ...y.map((v) => ({ value: v, group: 'y' })),
      ];
      combined.sort((a, b) => a.value - b.value);

      // Assign ranks (handling ties)
      let rank = 1;
      for (let i = 0; i < combined.length; i++) {
        let j = i;
        while (j < combined.length - 1 && combined[j + 1].value === combined[i].value) {
          j++;
        }
        const avgRank = (rank + rank + (j - i)) / 2;
        for (let k = i; k <= j; k++) {
          combined[k].rank = avgRank;
        }
        rank += j - i + 1;
        i = j;
      }

      // Calculate U statistic
      const n1 = x.length;
      const n2 = y.length;
      const r1 = combined.filter((c) => c.group === 'x').reduce((sum, c) => sum + c.rank, 0);

      const U1 = n1 * n2 + (n1 * (n1 + 1)) / 2 - r1;
      const U2 = n1 * n2 - U1;
      const U = Math.min(U1, U2);

      // Normal approximation for p-value
      const mu = (n1 * n2) / 2;
      const sigma = Math.sqrt((n1 * n2 * (n1 + n2 + 1)) / 12);
      const z = (U - mu) / sigma;
      const pValue = 2 * (1 - this.normalCDF(Math.abs(z)));

      // Effect sizes
      const pooledStd = Math.sqrt(
        ((n1 - 1) * Math.pow(this.pathogenicStats.stdDev, 2) +
          (n2 - 1) * Math.pow(this.vusStats.stdDev, 2)) /
          (n1 + n2 - 2)
      );
      const cohensD =
        pooledStd > 0 ? (this.pathogenicStats.mean - this.vusStats.mean) / pooledStd : 0;
      const rankBiserial = 1 - (2 * U) / (n1 * n2);

      return {
        U,
        z,
        pValue,
        cohensD: Math.abs(cohensD),
        rankBiserial: Math.abs(rankBiserial),
      };
    },

    normalCDF(x) {
      // Approximation of the standard normal CDF
      const a1 = 0.254829592;
      const a2 = -0.284496736;
      const a3 = 1.421413741;
      const a4 = -1.453152027;
      const a5 = 1.061405429;
      const p = 0.3275911;

      const sign = x < 0 ? -1 : 1;
      x = Math.abs(x) / Math.sqrt(2);

      const t = 1.0 / (1.0 + p * x);
      const y = 1.0 - ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);

      return 0.5 * (1.0 + sign * y);
    },

    renderBoxPlot() {
      if (!this.$refs.boxPlotContainer) {
        window.logService.warn('Box plot container not found');
        return;
      }

      // Check if we have data to render
      if (this.pathogenicDistances.length === 0 && this.vusDistances.length === 0) {
        window.logService.warn('No distance data available for box plot');
        return;
      }

      // Clear previous chart
      d3.select(this.$refs.boxPlotContainer).selectAll('*').remove();

      // Get container width - wait for proper sizing
      let containerWidth = this.$refs.boxPlotContainer.clientWidth;
      if (!containerWidth || containerWidth < 100) {
        containerWidth = this.width;
      }

      const margin = { top: 50, right: 40, bottom: 60, left: 70 };
      const width = containerWidth - margin.left - margin.right;
      const height = this.height - margin.top - margin.bottom;

      if (width <= 0 || height <= 0) {
        window.logService.warn('Invalid chart dimensions', { width, height });
        return;
      }

      const svg = d3
        .select(this.$refs.boxPlotContainer)
        .append('svg')
        .attr('width', containerWidth)
        .attr('height', this.height)
        .style('display', 'block');

      const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

      // Prepare data - filter out groups with no data
      const groups = [
        { name: 'P/LP', data: this.pathogenicDistances, color: '#D32F2F' },
        { name: 'VUS', data: this.vusDistances, color: '#FBC02D' },
      ].filter((group) => group.data.length > 0);

      if (groups.length === 0) {
        window.logService.warn('No groups with data for box plot');
        return;
      }

      // Scales
      const x = d3
        .scaleBand()
        .domain(groups.map((grp) => grp.name))
        .range([0, width])
        .padding(0.4);

      const allDistances = [...this.pathogenicDistances, ...this.vusDistances].map(
        (v) => v.distance
      );
      const yMax = (d3.max(allDistances) || 30) * 1.15;

      const y = d3.scaleLinear().domain([0, yMax]).range([height, 0]);

      // Axes
      g.append('g')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x))
        .selectAll('text')
        .style('font-size', '12px');

      g.append('g').call(d3.axisLeft(y).ticks(10)).selectAll('text').style('font-size', '11px');

      // Y-axis label
      g.append('text')
        .attr('transform', 'rotate(-90)')
        .attr('y', -45)
        .attr('x', -height / 2)
        .attr('text-anchor', 'middle')
        .style('font-size', '12px')
        .text('Distance to DNA (Å)');

      // Kernel density estimation function
      const kernelDensityEstimator = (kernel, X) => {
        return (V) => X.map((x) => [x, d3.mean(V, (v) => kernel(x - v))]);
      };

      const kernelEpanechnikov = (bandwidth) => {
        return (x) => (Math.abs((x /= bandwidth)) <= 1 ? (0.75 * (1 - x * x)) / bandwidth : 0);
      };

      // Draw violin + box plots
      groups.forEach((group) => {
        if (group.data.length === 0) return;

        const distances = group.data.map((v) => v.distance).sort((a, b) => a - b);
        const n = distances.length;

        const q1 = d3.quantile(distances, 0.25);
        const median = d3.quantile(distances, 0.5);
        const q3 = d3.quantile(distances, 0.75);
        const iqr = q3 - q1;
        const min = Math.max(distances[0], q1 - 1.5 * iqr);
        const max = Math.min(distances[n - 1], q3 + 1.5 * iqr);

        const boxWidth = x.bandwidth();
        const xPos = x(group.name);
        const centerX = xPos + boxWidth / 2;

        // Calculate kernel density for violin plot
        const bandwidth = iqr > 0 ? iqr / 1.34 : 1; // Silverman's rule of thumb
        const kde = kernelDensityEstimator(
          kernelEpanechnikov(bandwidth),
          y.ticks(40).map((t) => t)
        );
        const density = kde(distances);

        // Scale density to fit within the box width
        const maxDensity = d3.max(density, (d) => d[1]) || 1;
        const violinWidth = boxWidth * 0.9;
        const xScale = d3
          .scaleLinear()
          .domain([0, maxDensity])
          .range([0, violinWidth / 2]);

        // Draw violin shape (mirrored on both sides)
        const violinArea = d3
          .area()
          .x0((d) => centerX - xScale(d[1]))
          .x1((d) => centerX + xScale(d[1]))
          .y((d) => y(d[0]))
          .curve(d3.curveCatmullRom);

        g.append('path')
          .datum(density)
          .attr('d', violinArea)
          .attr('fill', group.color)
          .attr('fill-opacity', 0.15)
          .attr('stroke', group.color)
          .attr('stroke-width', 1)
          .attr('stroke-opacity', 0.5);

        // Box (narrower, overlaid on violin)
        const innerBoxWidth = boxWidth * 0.25;
        g.append('rect')
          .attr('x', centerX - innerBoxWidth / 2)
          .attr('y', y(q3))
          .attr('width', innerBoxWidth)
          .attr('height', y(q1) - y(q3))
          .attr('fill', group.color)
          .attr('fill-opacity', 0.5)
          .attr('stroke', group.color)
          .attr('stroke-width', 1.5);

        // Median line
        g.append('line')
          .attr('x1', centerX - innerBoxWidth / 2)
          .attr('x2', centerX + innerBoxWidth / 2)
          .attr('y1', y(median))
          .attr('y2', y(median))
          .attr('stroke', 'white')
          .attr('stroke-width', 2);

        // Whiskers (thinner vertical lines)
        g.append('line')
          .attr('x1', centerX)
          .attr('x2', centerX)
          .attr('y1', y(min))
          .attr('y2', y(q1))
          .attr('stroke', group.color)
          .attr('stroke-width', 1);

        g.append('line')
          .attr('x1', centerX)
          .attr('x2', centerX)
          .attr('y1', y(q3))
          .attr('y2', y(max))
          .attr('stroke', group.color)
          .attr('stroke-width', 1);

        // Individual points (jittered within violin shape) with tooltips
        // Use 85% of violin width for better spread and less overlap
        const jitterWidth = violinWidth * 0.85;
        const pointClass = `point-${group.name.replace(/[^a-zA-Z0-9]/g, '-')}`;

        // Create tooltip div if it doesn't exist
        let tooltip = d3.select('body').select('.dna-distance-tooltip');
        if (tooltip.empty()) {
          tooltip = d3
            .select('body')
            .append('div')
            .attr('class', 'dna-distance-tooltip')
            .style('position', 'absolute')
            .style('visibility', 'hidden')
            .style('background-color', 'rgba(0, 0, 0, 0.85)')
            .style('color', 'white')
            .style('padding', '8px 12px')
            .style('border-radius', '4px')
            .style('font-size', '12px')
            .style('pointer-events', 'none')
            .style('z-index', '1000')
            .style('max-width', '300px')
            .style('box-shadow', '0 2px 8px rgba(0,0,0,0.3)');
        }

        g.selectAll(`.${pointClass}`)
          .data(group.data)
          .enter()
          .append('circle')
          .attr('class', pointClass)
          .attr('cx', () => xPos + boxWidth / 2 + (Math.random() - 0.5) * jitterWidth)
          .attr('cy', (d) => y(d.distance))
          .attr('r', 4)
          .attr('fill', group.color)
          .attr('fill-opacity', 0.7)
          .attr('stroke', 'white')
          .attr('stroke-width', 1.5)
          .style('cursor', 'pointer')
          .on('mouseover', (event, d) => {
            d3.select(event.currentTarget)
              .attr('r', 6)
              .attr('fill-opacity', 1)
              .attr('stroke-width', 2);

            const variantLabel = d.protein || d.hgvs || d.label || `Position ${d.aaPosition}`;
            const classification = d.classificationVerdict || 'Unknown';

            tooltip
              .html(
                `<strong>${variantLabel}</strong><br/>` +
                  `Distance: <strong>${d.distance.toFixed(2)} Å</strong><br/>` +
                  `Position: ${d.aaPosition}<br/>` +
                  `Classification: ${classification}<br/>` +
                  `Category: ${this.getCategoryLabel(d.category)}`
              )
              .style('visibility', 'visible');
          })
          .on('mousemove', (event) => {
            tooltip.style('top', event.pageY - 10 + 'px').style('left', event.pageX + 15 + 'px');
          })
          .on('mouseout', (event) => {
            d3.select(event.currentTarget)
              .attr('r', 4)
              .attr('fill-opacity', 0.7)
              .attr('stroke-width', 1.5);

            tooltip.style('visibility', 'hidden');
          });
      });

      // Add significance bracket if significant
      if (this.pValueSignificant) {
        const bracketY = y(yMax * 0.95);

        g.append('line')
          .attr('x1', x('P/LP') + x.bandwidth() / 2)
          .attr('x2', x('VUS') + x.bandwidth() / 2)
          .attr('y1', bracketY)
          .attr('y2', bracketY)
          .attr('stroke', '#333')
          .attr('stroke-width', 1.5);

        g.append('line')
          .attr('x1', x('P/LP') + x.bandwidth() / 2)
          .attr('x2', x('P/LP') + x.bandwidth() / 2)
          .attr('y1', bracketY)
          .attr('y2', bracketY + 8)
          .attr('stroke', '#333')
          .attr('stroke-width', 1.5);

        g.append('line')
          .attr('x1', x('VUS') + x.bandwidth() / 2)
          .attr('x2', x('VUS') + x.bandwidth() / 2)
          .attr('y1', bracketY)
          .attr('y2', bracketY + 8)
          .attr('stroke', '#333')
          .attr('stroke-width', 1.5);

        g.append('text')
          .attr('x', (x('P/LP') + x('VUS') + x.bandwidth()) / 2)
          .attr('y', bracketY - 8)
          .attr('text-anchor', 'middle')
          .style('font-size', '12px')
          .style('font-weight', 'bold')
          .text(`p = ${this.formatPValue(this.mannWhitneyResult.pValue)}`);
      }

      // Title
      svg
        .append('text')
        .attr('x', containerWidth / 2)
        .attr('y', 20)
        .attr('text-anchor', 'middle')
        .style('font-size', '14px')
        .style('font-weight', 'bold')
        .text('DNA Distance by Pathogenicity Classification');
    },

    extractAAPosition(variant) {
      if (!variant.protein) return null;

      const pNotation = extractPNotation(variant.protein);
      if (!pNotation) return null;

      const match = pNotation.match(/p\.([A-Z][a-z]{2})?(\d+)/);
      if (match && match[2]) {
        return parseInt(match[2]);
      }

      return null;
    },

    formatPValue(pValue) {
      if (!pValue && pValue !== 0) return 'N/A';
      if (pValue < 0.0001) return '< 0.0001';
      if (pValue < 0.001) return pValue.toFixed(4);
      return pValue.toFixed(3);
    },

    getCategoryWidth(group, category) {
      const categories = group === 'pathogenic' ? this.pathogenicCategories : this.vusCategories;
      const total = categories.close + categories.medium + categories.far;
      if (total === 0) return 0;
      return (categories[category] / total) * 100;
    },

    getCategoryLabel(category) {
      if (category === 'close') return 'Close (<5Å)';
      if (category === 'medium') return 'Medium (5-10Å)';
      return 'Far (≥10Å)';
    },

    getEffectSizeColor(d) {
      const absD = Math.abs(d);
      if (absD >= 0.8) return 'error';
      if (absD >= 0.5) return 'warning';
      if (absD >= 0.2) return 'info';
      return 'grey';
    },

    getEffectSizeLabel(d) {
      const absD = Math.abs(d);
      if (absD >= 0.8) return 'Large';
      if (absD >= 0.5) return 'Medium';
      if (absD >= 0.2) return 'Small';
      return 'Negligible';
    },
  },
};
</script>

<style scoped>
.stat-card {
  height: 100%;
}

.chart-container {
  width: 100%;
  min-height: 400px;
}

.distance-distribution {
  display: flex;
  height: 28px;
  border-radius: 4px;
  overflow: hidden;
}

.distance-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 12px;
  font-weight: 500;
  min-width: 0;
  transition: width 0.3s ease;
}

.distance-bar.close {
  background-color: #d32f2f;
}

.distance-bar.medium {
  background-color: #ff9800;
}

.distance-bar.far {
  background-color: #4caf50;
}

.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 4px;
}

.legend-dot.close {
  background-color: #d32f2f;
}

.legend-dot.medium {
  background-color: #ff9800;
}

.legend-dot.far {
  background-color: #4caf50;
}

.h-100 {
  height: 100%;
}
</style>
