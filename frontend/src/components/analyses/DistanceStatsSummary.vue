<!-- Summary Statistics Cards for DNA Distance Analysis -->
<template>
  <v-row class="pa-3">
    <v-col cols="12" sm="6" md="3">
      <v-card variant="outlined" class="stat-card">
        <v-card-text class="text-center">
          <v-icon color="info" size="32">mdi-molecule</v-icon>
          <div class="text-h5 mt-2">{{ totalVariantsInStructure }}</div>
          <div class="text-caption text-grey">Variants in Structure</div>
          <div class="text-caption text-grey-darken-1">(residues 90-186, 231-308)</div>
        </v-card-text>
      </v-card>
    </v-col>
    <v-col cols="12" sm="6" md="3">
      <v-card variant="outlined" class="stat-card">
        <v-card-text class="text-center">
          <v-icon color="error" size="32">mdi-alert-circle</v-icon>
          <div v-if="pathogenicStats" class="text-h5 mt-2">
            {{ pathogenicStats.median.toFixed(1) }} &Aring;
          </div>
          <div class="text-caption text-grey">P/LP Median Distance</div>
          <div class="text-caption text-grey-darken-1">(n={{ pathogenicStats?.count || 0 }})</div>
        </v-card-text>
      </v-card>
    </v-col>
    <v-col cols="12" sm="6" md="3">
      <v-card variant="outlined" class="stat-card">
        <v-card-text class="text-center">
          <v-icon color="warning" size="32">mdi-help-circle</v-icon>
          <div v-if="vusStats" class="text-h5 mt-2">{{ vusStats.median.toFixed(1) }} &Aring;</div>
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
            {{ mannWhitneyResult ? formatPValueDisplay(mannWhitneyResult.pValue) : 'N/A' }}
          </div>
          <div class="text-caption text-grey">Mann-Whitney p-value</div>
          <div class="text-caption" :class="pValueSignificant ? 'text-success' : 'text-grey'">
            {{ pValueSignificant ? 'Significant (p < 0.05)' : 'Not significant' }}
          </div>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
</template>

<script>
import { formatPValue } from '@/utils/statistics';

export default {
  name: 'DistanceStatsSummary',
  props: {
    totalVariantsInStructure: {
      type: Number,
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
    mannWhitneyResult: {
      type: Object,
      default: null,
    },
    pValueSignificant: {
      type: Boolean,
      default: false,
    },
  },
  methods: {
    formatPValueDisplay(pValue) {
      return formatPValue(pValue);
    },
  },
};
</script>

<style scoped>
.stat-card {
  height: 100%;
}
</style>
