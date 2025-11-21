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
                    <v-col cols="12" md="3">
                      <v-select
                        v-model="comparisonLimit"
                        :items="comparisonLimitOptions"
                        item-title="label"
                        item-value="value"
                        label="Number of Phenotypes"
                      />
                    </v-col>
                    <v-col cols="12" md="3">
                      <v-select
                        v-model="minPrevalence"
                        :items="prevalenceOptions"
                        item-title="label"
                        item-value="value"
                        label="Minimum Prevalence"
                        hint="Minimum prevalence in at least one group"
                        persistent-hint
                      />
                    </v-col>
                    <v-col cols="12" md="2">
                      <v-select
                        v-model="sortBy"
                        :items="sortByOptions"
                        item-title="label"
                        item-value="value"
                        label="Sort By"
                      />
                    </v-col>
                  </v-row>

                  <!-- Reporting Mode Toggle -->
                  <v-row class="pa-3">
                    <v-col cols="12">
                      <v-select
                        v-model="reportingMode"
                        :items="reportingModeOptions"
                        item-title="label"
                        item-value="value"
                        label="Reporting Mode"
                        hint="Choose how to handle phenotypes that were not explicitly documented"
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
                    :width="1200"
                    :height="Math.max(400, comparisonData.phenotypes.length * 50 + 150)"
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
          label: 'Diseases',
          aggregations: [{ label: 'Disease Frequency', value: 'getDiseaseAggregation' }],
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
          aggregations: [{ label: 'Publication Statistics', value: 'getPublicationsAggregation' }],
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
      comparisonLimit: 20,
      minPrevalence: 0.05,
      sortBy: 'p_value',
      reportingMode: 'all_cases',
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
          description: 'Compare CAKUT vs CAKUT+MODY vs MODY phenotypes',
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
        { label: 'CNVs vs Non-CNV variants', value: 'cnv_vs_point_mutation' },
      ],
      allComparisonLimitOptions: [
        { label: 'Top 10', value: 10, threshold: 0 },
        { label: 'Top 20', value: 20, threshold: 0 },
        { label: 'Top 30', value: 30, threshold: 0 },
        { label: 'Top 50', value: 50, threshold: 50 },
        { label: 'All', value: 9999, threshold: 0 },
      ],
      prevalenceOptions: [
        { label: '1% (0.01)', value: 0.01 },
        { label: '5% (0.05)', value: 0.05 },
        { label: '10% (0.10)', value: 0.1 },
        { label: '20% (0.20)', value: 0.2 },
        { label: '30% (0.30)', value: 0.3 },
      ],
      sortByOptions: [
        { label: 'P-value (most significant first)', value: 'p_value' },
        { label: 'Effect size (largest first)', value: 'effect_size' },
        { label: 'Prevalence difference', value: 'prevalence_diff' },
      ],
      reportingModeOptions: [
        {
          label: 'All cases (assumes unreported = absent)',
          value: 'all_cases',
          description: 'Includes all patients; unreported phenotypes counted as absent',
        },
        {
          label: 'Reported only (excludes unreported)',
          value: 'reported_only',
          description: 'Only patients with explicit present/absent reporting',
        },
      ],
    };
  },
  computed: {
    donutChartProps() {
      return {
        content: this.items[0].content,
        props: { ...this.items[0].props, chartData: this.chartData },
      };
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
    comparisonLimitOptions() {
      // Filter options based on available comparison data
      // Only show "Top N" if we have more than N phenotypes
      const totalPhenotypes = this.comparisonData?.phenotypes?.length || 0;
      return this.allComparisonLimitOptions.filter((option) => {
        // Always show options with threshold 0 (Top 10, 20, 30, All)
        if (option.threshold === 0) return true;
        // Only show "Top 50" if we have more than 50 phenotypes
        return totalPhenotypes > option.threshold;
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
    comparisonLimit() {
      if (this.tab === 'Variant Comparison') {
        this.fetchComparisonData();
      }
    },
    minPrevalence() {
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
    reportingMode() {
      if (this.tab === 'Variant Comparison') {
        this.fetchComparisonData();
      }
    },
  },
  mounted() {
    this.fetchAggregationData();
    this.fetchStackedBarData();
  },
  methods: {
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

              // Build grouped counts
              groupedCounts = topItems.map((item) => ({
                _id: item.label || 'Unknown',
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
              // No limit, show all items
              groupedCounts = data.map((item) => ({
                _id: item.label || 'Unknown',
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
        limit: this.comparisonLimit,
        minPrevalence: this.minPrevalence,
        sortBy: this.sortBy,
        reportingMode: this.reportingMode,
      });

      try {
        const response = await API.compareVariantTypes({
          comparison: this.comparisonType,
          limit: this.comparisonLimit,
          min_prevalence: this.minPrevalence,
          sort_by: this.sortBy,
          reporting_mode: this.reportingMode,
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
  },
};
</script>

<style scoped>
/* Add view-specific styles if needed */
</style>
