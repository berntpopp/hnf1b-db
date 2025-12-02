<!-- Statistical Analysis Details Panel for DNA Distance Analysis -->
<template>
  <v-expansion-panels>
    <v-expansion-panel>
      <v-expansion-panel-title>
        <v-icon class="mr-2">mdi-chart-bell-curve</v-icon>
        Statistical Analysis Details
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <v-row>
          <!-- Pathogenic Stats -->
          <v-col cols="12" md="6">
            <h4 class="text-subtitle-1 font-weight-bold mb-2">Pathogenic / Likely Pathogenic</h4>
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
                  <td class="text-right">{{ pathogenicStats.median.toFixed(2) }} &Aring;</td>
                </tr>
                <tr>
                  <td>Std. Deviation</td>
                  <td class="text-right">{{ pathogenicStats.stdDev.toFixed(2) }} &Aring;</td>
                </tr>
                <tr>
                  <td>Min - Max</td>
                  <td class="text-right">
                    {{ pathogenicStats.min.toFixed(1) }} - {{ pathogenicStats.max.toFixed(1) }}
                    &Aring;
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

          <!-- VUS Stats -->
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
            <h4 class="text-subtitle-1 font-weight-bold mb-2">Effect Size & Test Details</h4>
            <v-table density="compact">
              <tbody>
                <tr>
                  <td>Median Difference (VUS - P/LP)</td>
                  <td class="text-right">
                    {{ medianDifference.toFixed(2) }} &Aring;
                    <v-chip
                      size="x-small"
                      :color="medianDifference > 0 ? 'success' : 'warning'"
                      class="ml-2"
                    >
                      {{ medianDifference > 0 ? 'P/LP closer to DNA' : 'VUS closer to DNA' }}
                    </v-chip>
                  </td>
                </tr>
                <tr>
                  <td>Rank-Biserial Correlation (r)</td>
                  <td class="text-right">
                    {{ mannWhitneyResult.rankBiserial.toFixed(3) }}
                    <v-chip
                      size="x-small"
                      :color="getRankBiserialColorDisplay(mannWhitneyResult.rankBiserial)"
                      class="ml-2"
                    >
                      {{ mannWhitneyResult.effectMagnitude }}
                    </v-chip>
                  </td>
                </tr>
                <tr>
                  <td>U Statistic</td>
                  <td class="text-right">{{ mannWhitneyResult.U.toFixed(0) }}</td>
                </tr>
                <tr>
                  <td>p-value</td>
                  <td class="text-right">
                    {{ formatPValueDisplay(mannWhitneyResult.pValue) }}
                    <v-chip
                      size="x-small"
                      :color="pValueSignificant ? 'success' : 'grey'"
                      class="ml-2"
                    >
                      {{ pValueSignificant ? 'significant' : 'not significant' }}
                    </v-chip>
                  </td>
                </tr>
                <tr>
                  <td>p-value Method</td>
                  <td class="text-right">
                    <v-chip size="x-small" color="grey-lighten-1">
                      {{ getPValueMethodLabel(mannWhitneyResult.method) }}
                    </v-chip>
                  </td>
                </tr>
                <tr v-if="mannWhitneyResult.tieCount > 0">
                  <td>Tied Groups</td>
                  <td class="text-right">{{ mannWhitneyResult.tieCount }}</td>
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
                  PDB 2H8R - HNF1B DNA-binding domain (UniProt P35680 residues 90-186 and 231-308;
                  linker region 187-230 not resolved)
                </v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon size="small" color="primary">mdi-ruler</v-icon>
                </template>
                <v-list-item-title class="text-body-2">Distance Calculation</v-list-item-title>
                <v-list-item-subtitle class="text-wrap">
                  Minimum Euclidean distance from any atom in the variant residue to any DNA atom
                  (closest-atom method)
                </v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon size="small" color="primary">mdi-chart-bell-curve</v-icon>
                </template>
                <v-list-item-title class="text-body-2">Statistical Test</v-list-item-title>
                <v-list-item-subtitle class="text-wrap">
                  Mann-Whitney U test (non-parametric, suitable for non-normal distributions)
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-col>
        </v-row>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>

<script>
import { formatPValue, getRankBiserialColor } from '@/utils/statistics';

export default {
  name: 'StatisticalDetailsPanel',
  props: {
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
  computed: {
    medianDifference() {
      if (!this.pathogenicStats || !this.vusStats) return 0;
      return this.vusStats.median - this.pathogenicStats.median;
    },
  },
  methods: {
    formatPValueDisplay(pValue) {
      return formatPValue(pValue);
    },
    getRankBiserialColorDisplay(r) {
      return getRankBiserialColor(r);
    },
    getPValueMethodLabel(method) {
      if (method === 'exact') return 'Exact';
      if (method === 'normal_tie_corrected') return 'Normal (tie-corrected)';
      return 'Normal approximation';
    },
  },
};
</script>
