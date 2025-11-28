<!-- src/views/AggregationsDashboard.vue -->
<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <v-sheet outlined>
          <v-card>
            <v-tabs v-model="tab" bg-color="primary">
              <v-tab value="Donut Chart"> Donut Chart </v-tab>
              <v-tab value="Stacked Bar Chart"> Stacked Bar Chart </v-tab>
              <v-tab value="Publications Timeline"> Publications Timeline </v-tab>
              <v-tab value="Variant Comparison"> Variant Comparison </v-tab>
              <v-tab value="Survival Curves"> Survival Curves </v-tab>
            </v-tabs>
            <v-card-text>
              <v-tabs-window v-model="tab">
                <!-- Donut Chart Tab -->
                <v-tabs-window-item value="Donut Chart">
                  <v-row class="pa-3">
                    <v-col
                      cols="12"
                      :sm="isVariantAggregation ? 6 : 12"
                      :md="isVariantAggregation ? 4 : 6"
                    >
                      <v-select
                        v-model="selectedCategory"
                        :items="donutCategories"
                        item-title="label"
                        item-value="label"
                        label="Category"
                        @change="onCategoryChange"
                      />
                    </v-col>
                    <v-col
                      cols="12"
                      :sm="isVariantAggregation ? 6 : 12"
                      :md="isVariantAggregation ? 4 : 6"
                    >
                      <v-select
                        v-model="selectedAggregation"
                        :items="selectedAggregations"
                        item-title="label"
                        item-value="value"
                        label="Aggregation"
                        @change="fetchAggregationData"
                      />
                    </v-col>
                    <v-col v-if="isVariantAggregation" cols="12" sm="6" md="4">
                      <v-select
                        v-model="variantCountMode"
                        :items="countModeOptions"
                        item-title="label"
                        item-value="value"
                        label="Count Mode"
                        hint="'All' counts variant instances (e.g., 864), 'Unique' counts distinct variants"
                        persistent-hint
                        @change="fetchAggregationData"
                      />
                    </v-col>
                  </v-row>
                  <component :is="donutChartProps.content" v-bind="donutChartProps.props" />
                </v-tabs-window-item>

                <!-- Stacked Bar Chart Tab -->
                <v-tabs-window-item value="Stacked Bar Chart">
                  <v-row class="pa-3">
                    <v-col cols="12" md="6">
                      <v-select
                        v-model="stackedBarDisplayLimit"
                        :items="displayLimitOptions"
                        item-title="label"
                        item-value="value"
                        label="Number of Features to Display"
                        @change="fetchStackedBarData"
                      />
                    </v-col>
                  </v-row>

                  <!-- Summary Statistics Panel -->
                  <v-row v-if="stackedBarStats" class="pa-3 pt-0">
                    <v-col cols="12">
                      <v-card outlined>
                        <v-card-title class="text-subtitle-1 py-2 bg-blue-lighten-5">
                          <v-icon left color="primary" size="small"> mdi-chart-box </v-icon>
                          Summary Statistics
                        </v-card-title>
                        <v-card-text class="pa-3">
                          <v-row dense>
                            <v-col cols="6" sm="3">
                              <div class="text-caption text-grey">Total Features</div>
                              <div class="text-h6">{{ stackedBarStats.totalFeatures }}</div>
                            </v-col>
                            <v-col cols="6" sm="3">
                              <div class="text-caption text-grey">Most Common</div>
                              <div class="text-body-2">
                                {{ stackedBarStats.mostCommon.label }}
                              </div>
                              <div class="text-caption">
                                {{ stackedBarStats.mostCommon.penetrance }}% penetrance
                              </div>
                            </v-col>
                            <v-col cols="6" sm="3">
                              <div class="text-caption text-grey">Avg. Penetrance</div>
                              <div class="text-h6">{{ stackedBarStats.avgPenetrance }}%</div>
                              <div class="text-caption">(when reported)</div>
                            </v-col>
                            <v-col cols="6" sm="3">
                              <div class="text-caption text-grey">Data Completeness</div>
                              <div class="text-h6">{{ stackedBarStats.reportingRate }}%</div>
                              <div class="text-caption">reporting rate</div>
                            </v-col>
                          </v-row>
                        </v-card-text>
                      </v-card>
                    </v-col>
                  </v-row>

                  <StackedBarChart
                    :chart-data="stackedBarChartData"
                    :display-limit="stackedBarDisplayLimit"
                    :width="1000"
                    :height="600"
                  />
                </v-tabs-window-item>

                <!-- Publications Timeline Tab -->
                <v-tabs-window-item value="Publications Timeline">
                  <PublicationsTimelineChart />
                </v-tabs-window-item>

                <!-- Variant Comparison Tab -->
                <v-tabs-window-item value="Variant Comparison">
                  <v-row class="pa-3">
                    <v-col cols="12" md="4">
                      <v-select
                        v-model="comparisonType"
                        :items="comparisonTypes"
                        item-title="label"
                        item-value="value"
                        label="Comparison Type"
                      />
                    </v-col>
                    <v-col cols="12" md="4">
                      <v-select
                        v-model="organSystemFilter"
                        :items="organSystemOptions"
                        item-title="label"
                        item-value="value"
                        label="Organ System"
                        hint="Filter phenotypes by affected organ system"
                        persistent-hint
                      />
                    </v-col>
                    <v-col cols="12" md="4">
                      <v-select
                        v-model="sortBy"
                        :items="sortByOptions"
                        item-title="label"
                        item-value="value"
                        label="Sort By"
                      />
                    </v-col>
                  </v-row>

                  <!-- Loading indicator -->
                  <v-row v-if="comparisonLoading" class="pa-3">
                    <v-col cols="12" class="text-center">
                      <v-progress-circular indeterminate color="primary" />
                      <p class="mt-2">Loading comparison data...</p>
                    </v-col>
                  </v-row>

                  <!-- Error message -->
                  <v-row v-else-if="comparisonError" class="pa-3">
                    <v-col cols="12">
                      <v-alert type="error" variant="tonal">
                        {{ comparisonError }}
                      </v-alert>
                    </v-col>
                  </v-row>

                  <!-- Chart -->
                  <VariantComparisonChart
                    v-else-if="comparisonData"
                    :comparison-data="comparisonData"
                    :comparison-type="comparisonType"
                    :organ-system-filter="organSystemFilter"
                    :width="1200"
                    :height="600"
                  />
                </v-tabs-window-item>

                <!-- Survival Curves Tab -->
                <v-tabs-window-item value="Survival Curves">
                  <v-row class="pa-3">
                    <v-col cols="12" md="6">
                      <v-select
                        v-model="survivalComparison"
                        :items="survivalComparisonTypes"
                        item-title="label"
                        item-value="value"
                        label="Comparison Type"
                        hint="Choose how to group patients for survival analysis"
                        persistent-hint
                      >
                        <template v-slot:item="{ props, item }">
                          <v-list-item v-bind="props">
                            <v-list-item-subtitle>
                              {{ item.raw.description }}
                            </v-list-item-subtitle>
                          </v-list-item>
                        </template>
                      </v-select>
                    </v-col>
                    <v-col cols="12" md="6">
                      <v-select
                        v-model="survivalEndpoint"
                        :items="survivalEndpointOptions"
                        item-title="label"
                        item-value="value"
                        label="Clinical Endpoint"
                        hint="Choose the clinical outcome to measure"
                        persistent-hint
                      >
                        <template v-slot:item="{ props, item }">
                          <v-list-item v-bind="props">
                            <v-list-item-subtitle>
                              {{ item.raw.description }}
                            </v-list-item-subtitle>
                          </v-list-item>
                        </template>
                      </v-select>
                    </v-col>
                  </v-row>

                  <!-- Loading indicator -->
                  <v-row v-if="survivalLoading" class="pa-3">
                    <v-col cols="12" class="text-center">
                      <v-progress-circular indeterminate color="primary" />
                      <p class="mt-2">Loading survival data...</p>
                    </v-col>
                  </v-row>

                  <!-- Error message -->
                  <v-row v-else-if="survivalError" class="pa-3">
                    <v-col cols="12">
                      <v-alert type="error" variant="tonal">
                        {{ survivalError }}
                      </v-alert>
                    </v-col>
                  </v-row>

                  <!-- Chart -->
                  <KaplanMeierChart
                    v-else-if="survivalData"
                    :survival-data="survivalData"
                    :width="1200"
                    :height="700"
                  />

                  <!-- Expandable Panels for Survival Data -->
                  <v-expansion-panels v-if="survivalData?.groups" class="mt-4">
                    <!-- Number at Risk Panel -->
                    <v-expansion-panel>
                      <v-expansion-panel-title>
                        <v-icon class="mr-2">mdi-account-group</v-icon>
                        Number at Risk
                      </v-expansion-panel-title>
                      <v-expansion-panel-text>
                        <v-table density="compact">
                          <thead>
                            <tr>
                              <th class="text-left" style="min-width: 120px">Group</th>
                              <th
                                v-for="time in riskTableTimePoints"
                                :key="time"
                                class="text-center"
                              >
                                {{ time }}y
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="group in survivalData.groups" :key="group.name">
                              <td class="font-weight-medium">{{ group.name }}</td>
                              <td
                                v-for="time in riskTableTimePoints"
                                :key="time"
                                class="text-center"
                              >
                                {{ getAtRiskCount(group, time) }}
                              </td>
                            </tr>
                          </tbody>
                        </v-table>
                        <p class="text-caption text-grey mt-2">
                          Number of patients still at risk (not yet experienced event or been
                          censored) at each time point.
                        </p>
                      </v-expansion-panel-text>
                    </v-expansion-panel>

                    <!-- Statistical Tests Panel -->
                    <v-expansion-panel v-if="survivalData?.statistical_tests?.length > 0">
                      <v-expansion-panel-title>
                        <v-icon class="mr-2">mdi-chart-bell-curve</v-icon>
                        Log-Rank Tests (Pairwise Comparisons)
                      </v-expansion-panel-title>
                      <v-expansion-panel-text>
                        <v-table density="compact">
                          <thead>
                            <tr>
                              <th class="text-left">Comparison</th>
                              <th class="text-center">χ² Statistic</th>
                              <th class="text-center">p-value (raw)</th>
                              <th class="text-center">p-value (corrected)</th>
                              <th class="text-center">Significant</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr
                              v-for="test in survivalData.statistical_tests"
                              :key="`${test.group1}-${test.group2}`"
                            >
                              <td>{{ test.group1 }} vs {{ test.group2 }}</td>
                              <td class="text-center">{{ test.statistic.toFixed(2) }}</td>
                              <td class="text-center text-grey">
                                {{ formatPValue(test.p_value) }}
                              </td>
                              <td
                                class="text-center"
                                :class="{ 'text-success font-weight-bold': test.significant }"
                              >
                                {{ formatPValue(test.p_value_corrected) }}
                              </td>
                              <td class="text-center">
                                <v-icon v-if="test.significant" color="success" size="small">
                                  mdi-check-circle
                                </v-icon>
                                <span v-else class="text-grey">—</span>
                              </td>
                            </tr>
                          </tbody>
                        </v-table>
                        <p class="text-caption text-grey mt-2">
                          Bonferroni-corrected p &lt; 0.05 considered statistically significant
                          (marked with
                          <v-icon size="x-small" color="success">mdi-check-circle</v-icon>).
                          Correction: p × {{ survivalData.statistical_tests?.length || 1 }}
                          comparisons.
                        </p>
                      </v-expansion-panel-text>
                    </v-expansion-panel>

                    <!-- Methodology Info Panel -->
                    <v-expansion-panel v-if="survivalData?.metadata">
                      <v-expansion-panel-title>
                        <v-icon class="mr-2">mdi-information-outline</v-icon>
                        Analysis Methodology & Group Definitions
                      </v-expansion-panel-title>
                      <v-expansion-panel-text>
                        <v-row>
                          <v-col cols="12" md="6">
                            <h4 class="text-subtitle-1 font-weight-bold mb-2">Event & Censoring</h4>
                            <v-list density="compact" class="bg-transparent">
                              <v-list-item>
                                <template v-slot:prepend>
                                  <v-icon size="small" color="error">mdi-alert-circle</v-icon>
                                </template>
                                <v-list-item-title class="text-body-2"
                                  >Event Definition</v-list-item-title
                                >
                                <v-list-item-subtitle class="text-wrap">
                                  {{ survivalData.metadata.event_definition }}
                                </v-list-item-subtitle>
                              </v-list-item>
                              <v-list-item>
                                <template v-slot:prepend>
                                  <v-icon size="small" color="info">mdi-clock-outline</v-icon>
                                </template>
                                <v-list-item-title class="text-body-2">Time Axis</v-list-item-title>
                                <v-list-item-subtitle class="text-wrap">
                                  {{ survivalData.metadata.time_axis }}
                                </v-list-item-subtitle>
                              </v-list-item>
                              <v-list-item>
                                <template v-slot:prepend>
                                  <v-icon size="small" color="warning">mdi-eye-off-outline</v-icon>
                                </template>
                                <v-list-item-title class="text-body-2">Censoring</v-list-item-title>
                                <v-list-item-subtitle class="text-wrap">
                                  {{ survivalData.metadata.censoring }}
                                </v-list-item-subtitle>
                              </v-list-item>
                            </v-list>
                          </v-col>
                          <v-col cols="12" md="6">
                            <h4 class="text-subtitle-1 font-weight-bold mb-2">
                              Inclusion & Exclusion Criteria
                            </h4>
                            <v-list density="compact" class="bg-transparent">
                              <v-list-item>
                                <template v-slot:prepend>
                                  <v-icon size="small" color="success">mdi-check-circle</v-icon>
                                </template>
                                <v-list-item-title class="text-body-2">Included</v-list-item-title>
                                <v-list-item-subtitle class="text-wrap">
                                  {{ survivalData.metadata.inclusion_criteria }}
                                </v-list-item-subtitle>
                              </v-list-item>
                              <v-list-item>
                                <template v-slot:prepend>
                                  <v-icon size="small" color="error">mdi-close-circle</v-icon>
                                </template>
                                <v-list-item-title class="text-body-2">Excluded</v-list-item-title>
                                <v-list-item-subtitle class="text-wrap">
                                  {{ survivalData.metadata.exclusion_criteria }}
                                </v-list-item-subtitle>
                              </v-list-item>
                            </v-list>
                          </v-col>
                        </v-row>

                        <!-- Group Definitions -->
                        <h4 class="text-subtitle-1 font-weight-bold mt-4 mb-2">
                          Group Definitions
                        </h4>
                        <v-table density="compact">
                          <thead>
                            <tr>
                              <th class="text-left" style="width: 150px">Group</th>
                              <th class="text-left">Definition</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr
                              v-for="(definition, groupName) in survivalData.metadata
                                .group_definitions"
                              :key="groupName"
                            >
                              <td class="font-weight-medium">{{ groupName }}</td>
                              <td class="text-body-2">{{ definition }}</td>
                            </tr>
                          </tbody>
                        </v-table>
                      </v-expansion-panel-text>
                    </v-expansion-panel>
                  </v-expansion-panels>
                </v-tabs-window-item>
              </v-tabs-window>
            </v-card-text>
          </v-card>
        </v-sheet>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
import { markRaw } from 'vue';
import DonutChart from '@/components/analyses/DonutChart.vue';
import StackedBarChart from '@/components/analyses/StackedBarChart.vue';
import PublicationsTimelineChart from '@/components/analyses/PublicationsTimelineChart.vue';
import VariantComparisonChart from '@/components/analyses/VariantComparisonChart.vue';
import KaplanMeierChart from '@/components/analyses/KaplanMeierChart.vue';
import * as API from '@/api';

export default {
  name: 'AggregationsDashboard',
  components: {
    DonutChart,
    PublicationsTimelineChart,
    StackedBarChart,
    VariantComparisonChart,
    KaplanMeierChart,
  },
  data() {
    return {
      tab: 'Donut Chart',
      chartData: {},
      stackedBarChartData: [],
      stackedBarDisplayLimit: 20,
      // Semantic color maps for specific aggregations
      colorMaps: {
        // Pathogenicity: red=pathogenic, orange=LP, yellow=VUS, green=benign
        getVariantPathogenicity: {
          Pathogenic: '#D32F2F', // Red
          'Likely Pathogenic': '#FF9800', // Orange
          'Uncertain Significance': '#FDD835', // Bright yellow for VUS
          'Likely Benign': '#81C784', // Light green
          Benign: '#388E3C', // Dark green
        },
        // Variant types
        getVariantTypes: {
          'Copy Number Loss': '#D32F2F', // Red
          'Copy Number Gain': '#1976D2', // Blue
          SNV: '#388E3C', // Green
          Deletion: '#FF9800', // Orange
          Duplication: '#9C27B0', // Purple
          Insertion: '#00BCD4', // Cyan
          Indel: '#E91E63', // Pink
          NA: '#9E9E9E', // Grey
        },
        // Sex distribution
        getSexDistribution: {
          MALE: '#1976D2', // Blue
          FEMALE: '#E91E63', // Pink
          OTHER_SEX: '#9C27B0', // Purple
          UNKNOWN_SEX: '#9E9E9E', // Grey
        },
        // Publication types
        getPublicationTypes: {
          'Case Series': '#1976D2', // Blue
          Research: '#4CAF50', // Green
          'Case Report': '#FF9800', // Orange
          'Review And Cases': '#9C27B0', // Purple
          'Screening Multiple': '#00BCD4', // Cyan
          Review: '#F44336', // Red
        },
      },
      items: [
        {
          tab: 'Donut Chart',
          content: markRaw(DonutChart),
          props: { exportable: true, width: 600, height: 500 },
        },
      ],
      donutCategories: [
        {
          label: 'Phenopackets',
          aggregations: [
            { label: 'Sex Distribution', value: 'getSexDistribution' },
            { label: 'Age of Onset', value: 'getAgeOfOnsetAggregation' },
            { label: 'Kidney Disease Stages', value: 'getKidneyStages' },
          ],
        },
        {
          label: 'Variants',
          aggregations: [
            {
              label: 'Pathogenicity Classification',
              value: 'getVariantPathogenicity',
              supportsCountMode: true,
            },
            {
              label: 'Variant Types (SNV/Indel/CNV)',
              value: 'getVariantTypes',
              supportsCountMode: true,
            },
          ],
        },
        {
          label: 'Publications',
          aggregations: [{ label: 'Publication Types', value: 'getPublicationTypes' }],
        },
      ],
      selectedCategory: 'Phenopackets',
      selectedAggregation: 'getSexDistribution',
      variantCountMode: 'all',
      countModeOptions: [
        { label: 'All Variant Instances', value: 'all' },
        { label: 'Unique Variants', value: 'unique' },
      ],
      allDisplayLimitOptions: [
        { label: 'Top 10', value: 10, threshold: 10 },
        { label: 'Top 20', value: 20, threshold: 20 },
        { label: 'Top 30', value: 30, threshold: 30 },
        { label: 'Top 50', value: 50, threshold: 50 },
        { label: 'All Features', value: 9999, threshold: 0 },
      ],
      // Variant Comparison data
      comparisonType: 'truncating_vs_non_truncating',
      sortBy: 'p_value',
      comparisonData: null,
      comparisonLoading: false,
      comparisonError: null,
      // Survival Curves data
      survivalComparison: 'variant_type',
      survivalEndpoint: 'ckd_stage_3_plus',
      survivalData: null,
      survivalLoading: false,
      survivalError: null,
      survivalComparisonTypes: [
        {
          label: 'Variant Type',
          value: 'variant_type',
          description: 'Compare CNV vs Truncating vs Non-truncating variants',
        },
        {
          label: 'Pathogenicity',
          value: 'pathogenicity',
          description: 'Compare Pathogenic/Likely Pathogenic vs VUS',
        },
        {
          label: 'Disease Subtype',
          value: 'disease_subtype',
          description: 'Compare CAKUT vs CAKUT+MODY vs MODY vs Other phenotypes',
        },
      ],
      survivalEndpointOptions: [
        {
          label: 'CKD Stage 3+ (GFR <60)',
          value: 'ckd_stage_3_plus',
          description: 'Time to CKD Stage 3 or higher (composite endpoint)',
        },
        {
          label: 'Stage 5 CKD (ESRD)',
          value: 'stage_5_ckd',
          description: 'Time to End-Stage Renal Disease (historical endpoint)',
        },
        {
          label: 'Any CKD',
          value: 'any_ckd',
          description: 'Time to any chronic kidney disease diagnosis',
        },
        {
          label: 'Age at Last Follow-up',
          value: 'current_age',
          description: 'Current/reported age (universal endpoint)',
        },
      ],
      comparisonTypes: [
        { label: 'Truncating vs Non-truncating', value: 'truncating_vs_non_truncating' },
        {
          label: 'Truncating vs Non-truncating (excl. CNVs)',
          value: 'truncating_vs_non_truncating_excl_cnv',
        },
        { label: 'CNVs vs Non-CNV variants', value: 'cnv_vs_point_mutation' },
      ],
      sortByOptions: [
        { label: 'P-value (most significant first)', value: 'p_value' },
        { label: 'Effect size (largest first)', value: 'effect_size' },
        { label: 'Prevalence difference', value: 'prevalence_diff' },
      ],
      organSystemFilter: 'all',
      organSystemOptions: [
        { label: 'All Systems', value: 'all' },
        { label: 'Renal', value: 'renal' },
        { label: 'Metabolic', value: 'metabolic' },
        { label: 'Neurological', value: 'neurological' },
        { label: 'Pancreatic/Endocrine', value: 'pancreatic' },
        { label: 'Other', value: 'other' },
      ],
    };
  },
  computed: {
    donutChartProps() {
      // Get the color map for the current aggregation if available
      const colorMap = this.colorMaps[this.selectedAggregation] || null;
      return {
        content: this.items[0].content,
        props: { ...this.items[0].props, chartData: this.chartData, colorMap },
      };
    },
    riskTableTimePoints() {
      if (!this.survivalData?.groups?.length) return [];
      // Find max time across all groups
      let maxTime = 0;
      this.survivalData.groups.forEach((group) => {
        group.survival_data.forEach((d) => {
          if (d.time > maxTime) maxTime = d.time;
        });
      });
      // Generate time points (every few years)
      const step = Math.ceil(maxTime / 8);
      const points = [];
      for (let t = 0; t <= maxTime; t += step) {
        points.push(t);
      }
      return points;
    },
    selectedAggregations() {
      const category = this.donutCategories.find((cat) => cat.label === this.selectedCategory);
      return category ? category.aggregations : [];
    },
    isVariantAggregation() {
      const category = this.donutCategories.find((cat) => cat.label === this.selectedCategory);
      const aggregation = category?.aggregations.find(
        (agg) => agg.value === this.selectedAggregation
      );
      return aggregation?.supportsCountMode || false;
    },
    displayLimitOptions() {
      // Filter options based on available data
      // Only show "Top N" if we have more than N features
      const totalFeatures = this.stackedBarChartData.length;
      return this.allDisplayLimitOptions.filter((option) => {
        // Always show "All Features" option
        if (option.threshold === 0) return true;
        // Only show "Top N" if we have more than N features
        return totalFeatures > option.threshold;
      });
    },
    stackedBarStats() {
      if (!this.stackedBarChartData || this.stackedBarChartData.length === 0) {
        return null;
      }

      const data = this.stackedBarChartData;

      // Calculate total features
      const totalFeatures = data.length;

      // Calculate most common feature (highest present count)
      const mostCommon = data.reduce((max, feature) => {
        const present = feature.details?.present_count || 0;
        const maxPresent = max.details?.present_count || 0;
        return present > maxPresent ? feature : max;
      }, data[0]);

      const mostCommonPresent = mostCommon.details?.present_count || 0;
      const mostCommonAbsent = mostCommon.details?.absent_count || 0;
      const mostCommonReported = mostCommonPresent + mostCommonAbsent;
      const mostCommonPenetrance =
        mostCommonReported > 0
          ? ((mostCommonPresent / mostCommonReported) * 100).toFixed(1)
          : '0.0';

      // Calculate average penetrance across all features
      let totalPenetrance = 0;
      let featuresWithReports = 0;

      data.forEach((feature) => {
        const present = feature.details?.present_count || 0;
        const absent = feature.details?.absent_count || 0;
        const reported = present + absent;

        if (reported > 0) {
          totalPenetrance += (present / reported) * 100;
          featuresWithReports++;
        }
      });

      const avgPenetrance =
        featuresWithReports > 0 ? (totalPenetrance / featuresWithReports).toFixed(1) : '0.0';

      // Calculate data completeness (reporting rate)
      let totalPresent = 0;
      let totalAbsent = 0;
      let totalNotReported = 0;

      data.forEach((feature) => {
        totalPresent += feature.details?.present_count || 0;
        totalAbsent += feature.details?.absent_count || 0;
        totalNotReported += feature.details?.not_reported_count || 0;
      });

      const totalDataPoints = totalPresent + totalAbsent + totalNotReported;
      const reportingRate =
        totalDataPoints > 0
          ? (((totalPresent + totalAbsent) / totalDataPoints) * 100).toFixed(1)
          : '0.0';

      return {
        totalFeatures,
        mostCommon: {
          label: mostCommon.label || 'N/A',
          penetrance: mostCommonPenetrance,
        },
        avgPenetrance,
        reportingRate,
      };
    },
  },
  watch: {
    selectedAggregation() {
      this.fetchAggregationData();
    },
    selectedCategory() {
      const aggregations = this.selectedAggregations;
      if (aggregations.length > 0) {
        this.selectedAggregation = aggregations[0].value;
      } else {
        this.selectedAggregation = null;
      }
      this.fetchAggregationData();
    },
    variantCountMode() {
      this.fetchAggregationData();
    },
    tab(newTab) {
      // Auto-fetch comparison data when switching to Variant Comparison tab
      if (newTab === 'Variant Comparison' && !this.comparisonData) {
        this.fetchComparisonData();
      }
      // Auto-fetch survival data when switching to Survival Curves tab
      if (newTab === 'Survival Curves' && !this.survivalData) {
        this.fetchSurvivalData();
      }
    },
    // Watch comparison parameters and refetch data
    comparisonType() {
      if (this.tab === 'Variant Comparison') {
        this.fetchComparisonData();
      }
    },
    sortBy() {
      if (this.tab === 'Variant Comparison') {
        this.fetchComparisonData();
      }
    },
    // Watch survival parameters and refetch data
    survivalComparison() {
      if (this.tab === 'Survival Curves') {
        this.fetchSurvivalData();
      }
    },
    survivalEndpoint() {
      if (this.tab === 'Survival Curves') {
        this.fetchSurvivalData();
      }
    },
  },
  mounted() {
    this.fetchAggregationData();
    this.fetchStackedBarData();
  },
  methods: {
    /**
     * Format API labels to human-readable display labels.
     * Converts UPPER_SNAKE_CASE to Title Case (e.g., LIKELY_PATHOGENIC -> Likely Pathogenic)
     */
    formatLabel(label) {
      if (!label) return 'Unknown';
      // Replace underscores with spaces and convert to title case
      return label
        .split('_')
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ');
    },

    fetchStackedBarData() {
      window.logService.debug('Fetching stacked bar chart data');

      API.getPhenotypicFeaturesAggregation()
        .then((response) => {
          window.logService.info('Stacked bar chart data loaded', {
            count: response.data?.length,
          });

          this.stackedBarChartData = response.data || [];
        })
        .catch((error) => {
          window.logService.error('Error fetching stacked bar chart data', {
            error: error.message,
          });
        });
    },

    fetchAggregationData() {
      const category = this.donutCategories.find((cat) => cat.label === this.selectedCategory);
      const aggregation = category?.aggregations.find(
        (agg) => agg.value === this.selectedAggregation
      );
      const funcName = this.selectedAggregation;
      const params = { ...(aggregation?.params || {}) };

      // Add count_mode parameter if this is a variant aggregation
      if (aggregation?.supportsCountMode) {
        params.count_mode = this.variantCountMode;
      }

      window.logService.debug('Fetching aggregation data', {
        category: this.selectedCategory,
        aggregation: aggregation?.label,
        funcName: funcName,
        params: params,
        supportsCountMode: aggregation?.supportsCountMode || false,
      });

      if (API[funcName] && typeof API[funcName] === 'function') {
        API[funcName](params)
          .then((response) => {
            window.logService.info('Donut chart data loaded', {
              aggregation: aggregation.title,
              count: response.data?.length,
            });

            window.logService.debug('Transforming aggregation data for chart', {
              rawDataCount: response.data?.length || 0,
              totalCount: response.data?.reduce((sum, item) => sum + item.count, 0) || 0,
              hasLimit: !!params.limit,
              limit: params.limit,
            });

            // Transform v2 API format to DonutChart format
            // v2 API: [{ label: "X", count: 10, percentage: 50 }, ...]
            // DonutChart expects: { total_count: N, grouped_counts: [{ _id: "X", count: 10 }, ...] }
            let data = response.data || [];
            const totalCount = data.reduce((sum, item) => sum + item.count, 0);

            let groupedCounts = [];

            // Apply client-side limit if specified and add "Others" category
            if (params.limit && data.length > params.limit) {
              // Take top N items
              const topItems = data.slice(0, params.limit);
              const remainingItems = data.slice(params.limit);

              // Sum up remaining items into "Others"
              const othersCount = remainingItems.reduce((sum, item) => sum + item.count, 0);

              window.logService.debug('Applied client-side limit to data', {
                originalCount: data.length,
                limitedCount: topItems.length,
                othersCount: othersCount,
              });

              // Build grouped counts with formatted labels
              groupedCounts = topItems.map((item) => ({
                _id: this.formatLabel(item.label),
                count: item.count || 0,
              }));

              // Add "Others" category if there are remaining items
              if (othersCount > 0) {
                groupedCounts.push({
                  _id: 'Others',
                  count: othersCount,
                });
              }
            } else {
              // No limit, show all items with formatted labels
              groupedCounts = data.map((item) => ({
                _id: this.formatLabel(item.label),
                count: item.count || 0,
              }));
            }

            this.chartData = {
              total_count: totalCount,
              grouped_counts: groupedCounts,
            };
          })
          .catch((error) => {
            window.logService.error('Error fetching donut chart data', {
              error: error.message,
            });
          });
      } else {
        window.logService.error('API function not found', { funcName });
      }
    },
    onCategoryChange() {
      // Handled by watcher.
    },

    async fetchComparisonData() {
      this.comparisonLoading = true;
      this.comparisonError = null;

      window.logService.debug('Fetching variant comparison data', {
        comparisonType: this.comparisonType,
        sortBy: this.sortBy,
      });

      try {
        // Fetch all phenotypes (limit=100 is max allowed by API)
        // Client-side organ system filtering handles the display
        const response = await API.compareVariantTypes({
          comparison: this.comparisonType,
          limit: 100,
          min_prevalence: 0,
          sort_by: this.sortBy,
        });

        this.comparisonData = response.data;

        window.logService.info('Variant comparison data loaded', {
          groupNames: `${response.data.group1_name} vs ${response.data.group2_name}`,
          group1Count: response.data.group1_count,
          group2Count: response.data.group2_count,
          phenotypesCount: response.data.phenotypes?.length || 0,
          significantCount: response.data.metadata?.significant_count || 0,
        });
      } catch (error) {
        window.logService.error('Error fetching variant comparison data', {
          error: error.message,
        });
        this.comparisonError =
          error.response?.data?.detail || 'Failed to load comparison data. Please try again.';
      } finally {
        this.comparisonLoading = false;
      }
    },

    async fetchSurvivalData() {
      this.survivalLoading = true;
      this.survivalError = null;

      window.logService.debug('Fetching survival data', {
        comparison: this.survivalComparison,
        endpoint: this.survivalEndpoint,
      });

      try {
        const response = await API.getSurvivalData({
          comparison: this.survivalComparison,
          endpoint: this.survivalEndpoint,
        });

        this.survivalData = response.data;

        window.logService.info('Survival data loaded', {
          comparisonType: response.data.comparison_type,
          endpoint: response.data.endpoint,
          groupsCount: response.data.groups?.length || 0,
          statisticalTestsCount: response.data.statistical_tests?.length || 0,
        });
      } catch (error) {
        window.logService.error('Error fetching survival data', {
          error: error.message,
        });
        this.survivalError =
          error.response?.data?.detail || 'Failed to load survival data. Please try again.';
      } finally {
        this.survivalLoading = false;
      }
    },

    getAtRiskCount(group, time) {
      // Find the data point at or just before the given time
      const dataPoint = group.survival_data
        .filter((d) => d.time <= time)
        .sort((a, b) => b.time - a.time)[0];
      return dataPoint ? dataPoint.at_risk : '—';
    },

    formatPValue(pValue) {
      if (pValue < 0.0001) return '< 0.0001';
      return pValue.toFixed(4);
    },
  },
};
</script>

<style scoped>
/* Add view-specific styles if needed */
</style>
