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
      <DistanceStatsSummary
        :total-variants-in-structure="totalVariantsInStructure"
        :pathogenic-stats="pathogenicStats"
        :vus-stats="vusStats"
        :mann-whitney-result="mannWhitneyResult"
        :p-value-significant="pValueSignificant"
      />

      <!-- Visualization Row -->
      <v-row class="pa-3">
        <!-- Box Plot / Violin Plot -->
        <v-col cols="12" md="7">
          <v-card variant="outlined">
            <v-card-title class="text-subtitle-1 py-2 bg-blue-lighten-5">
              <v-icon left color="primary" size="small">mdi-chart-box</v-icon>
              Distance Distribution by Pathogenicity
            </v-card-title>
            <v-card-text>
              <BoxPlotChart
                :pathogenic-distances="pathogenicDistances"
                :vus-distances="vusDistances"
                :p-value-significant="pValueSignificant"
                :mann-whitney-result="mannWhitneyResult"
                :width="width"
                :height="height"
              />
            </v-card-text>
          </v-card>
        </v-col>

        <!-- Distance Category Breakdown -->
        <v-col cols="12" md="5">
          <DistanceCategoryBreakdown
            :pathogenic-categories="pathogenicCategories"
            :vus-categories="vusCategories"
            :pathogenic-stats="pathogenicStats"
            :vus-stats="vusStats"
            :mann-whitney-p-value="mannWhitneyResult?.pValue"
            :p-value-significant="pValueSignificant"
          />
        </v-col>
      </v-row>

      <!-- Statistical Details Panel -->
      <v-row class="pa-3">
        <v-col cols="12">
          <StatisticalDetailsPanel
            :pathogenic-stats="pathogenicStats"
            :vus-stats="vusStats"
            :mann-whitney-result="mannWhitneyResult"
            :p-value-significant="pValueSignificant"
          />
        </v-col>
      </v-row>
    </template>
  </v-container>
</template>

<script>
import * as NGL from 'ngl';
import { markRaw } from 'vue';
import { getVariants } from '@/api';
import { extractPNotation } from '@/utils/hgvs';
import {
  DNADistanceCalculator,
  STRUCTURE_START,
  STRUCTURE_END,
} from '@/utils/dnaDistanceCalculator';
import { matchesPathogenicityCategory } from '@/utils/colors';
import { calculateDescriptiveStats, mannWhitneyU as mannWhitneyUTest } from '@/utils/statistics';
import BoxPlotChart from './BoxPlotChart.vue';
import DistanceStatsSummary from './DistanceStatsSummary.vue';
import DistanceCategoryBreakdown from './DistanceCategoryBreakdown.vue';
import StatisticalDetailsPanel from './StatisticalDetailsPanel.vue';

// Store NGL objects outside Vue's reactivity system
let nglStage = null;
let nglStructureComponent = null;
let distanceCalculator = null;

export default {
  name: 'DNADistanceAnalysis',
  components: {
    BoxPlotChart,
    DistanceStatsSummary,
    DistanceCategoryBreakdown,
    StatisticalDetailsPanel,
  },
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

        // 5. Mark loading complete
        this.loading = false;

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
      this.pathogenicDistances = variantsWithDistances.filter(
        (v) =>
          matchesPathogenicityCategory(v.classificationVerdict, 'PATHOGENIC') ||
          matchesPathogenicityCategory(v.classificationVerdict, 'LIKELY_PATHOGENIC')
      );

      this.vusDistances = variantsWithDistances.filter((v) =>
        matchesPathogenicityCategory(v.classificationVerdict, 'VUS')
      );

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
      // Calculate statistics for each group using utility function
      const pathogenicDistanceValues = this.pathogenicDistances.map((v) => v.distance);
      const vusDistanceValues = this.vusDistances.map((v) => v.distance);

      this.pathogenicStats = calculateDescriptiveStats(pathogenicDistanceValues);
      this.vusStats = calculateDescriptiveStats(vusDistanceValues);

      // Perform Mann-Whitney U test using utility function
      if (this.pathogenicDistances.length >= 3 && this.vusDistances.length >= 3) {
        this.mannWhitneyResult = mannWhitneyUTest(pathogenicDistanceValues, vusDistanceValues);
      }
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
  },
};
</script>
