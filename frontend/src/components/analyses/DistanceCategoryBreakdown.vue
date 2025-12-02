<!-- Distance Category Breakdown for DNA Distance Analysis -->
<template>
  <v-card variant="outlined" class="h-100">
    <v-card-title class="text-subtitle-1 py-2 bg-orange-lighten-5">
      <v-icon left color="orange" size="small">mdi-chart-donut</v-icon>
      Distance Categories by Group
    </v-card-title>
    <v-card-text>
      <!-- P/LP Distribution -->
      <div class="mb-4">
        <div class="text-body-2 font-weight-medium mb-1">Pathogenic / Likely Pathogenic</div>
        <div class="distance-distribution">
          <div
            v-for="cat in categories"
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
        <div class="text-body-2 font-weight-medium mb-1">Variants of Uncertain Significance</div>
        <div class="distance-distribution">
          <div
            v-for="cat in categories"
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
            {{ formatPValueDisplay(mannWhitneyPValue) }}), suggesting that proximity to DNA may
            correlate with pathogenicity.
          </span>
          <span v-else> This difference is not statistically significant at p &lt; 0.05. </span>
        </div>
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script>
import { formatPValue } from '@/utils/statistics';

export default {
  name: 'DistanceCategoryBreakdown',
  props: {
    pathogenicCategories: {
      type: Object,
      required: true,
    },
    vusCategories: {
      type: Object,
      required: true,
    },
    pathogenicStats: {
      type: Object,
      default: null,
    },
    vusStats: {
      type: Object,
      default: null,
    },
    mannWhitneyPValue: {
      type: Number,
      default: null,
    },
    pValueSignificant: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      categories: ['close', 'medium', 'far'],
    };
  },
  methods: {
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
    formatPValueDisplay(pValue) {
      return formatPValue(pValue);
    },
  },
};
</script>

<style scoped>
.h-100 {
  height: 100%;
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
</style>
