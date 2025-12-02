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
              <v-tab value="DNA Distance Analysis"> DNA Distance Analysis </v-tab>
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
                    :width="1200"
                    :height="800"
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
                        <template #item="{ props, item }">
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
                        <template #item="{ props, item }">
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
                  <SurvivalDataPanels :survival-data="survivalData" />
                </v-tabs-window-item>

                <!-- DNA Distance Analysis Tab -->
                <v-tabs-window-item value="DNA Distance Analysis">
                  <DNADistanceAnalysis :width="1200" :height="450" />
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
import DNADistanceAnalysis from '@/components/analyses/DNADistanceAnalysis.vue';
import SurvivalDataPanels from '@/components/analyses/SurvivalDataPanels.vue';
import * as API from '@/api';
import {
  AGGREGATION_COLOR_MAPS,
  DONUT_CATEGORIES,
  COUNT_MODE_OPTIONS,
  DISPLAY_LIMIT_OPTIONS,
  COMPARISON_TYPES,
  SORT_BY_OPTIONS,
  ORGAN_SYSTEM_OPTIONS,
  SURVIVAL_COMPARISON_TYPES,
  SURVIVAL_ENDPOINT_OPTIONS,
  formatLabel as formatLabelUtil,
  calculateStackedBarStats,
} from '@/utils/aggregationConfig';

export default {
  name: 'AggregationsDashboard',
  components: {
    DonutChart,
    PublicationsTimelineChart,
    StackedBarChart,
    VariantComparisonChart,
    KaplanMeierChart,
    DNADistanceAnalysis,
    SurvivalDataPanels,
  },
  data() {
    return {
      tab: 'Donut Chart',
      chartData: {},
      stackedBarChartData: [],
      stackedBarDisplayLimit: 20,
      // Use imported configuration constants
      colorMaps: AGGREGATION_COLOR_MAPS,
      items: [
        {
          tab: 'Donut Chart',
          content: markRaw(DonutChart),
          props: { exportable: true, width: 600, height: 500 },
        },
      ],
      donutCategories: DONUT_CATEGORIES,
      selectedCategory: 'Phenopackets',
      selectedAggregation: 'getSexDistribution',
      variantCountMode: 'all',
      countModeOptions: COUNT_MODE_OPTIONS,
      allDisplayLimitOptions: DISPLAY_LIMIT_OPTIONS,
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
      survivalComparisonTypes: SURVIVAL_COMPARISON_TYPES,
      survivalEndpointOptions: SURVIVAL_ENDPOINT_OPTIONS,
      comparisonTypes: COMPARISON_TYPES,
      sortByOptions: SORT_BY_OPTIONS,
      organSystemFilter: 'all',
      organSystemOptions: ORGAN_SYSTEM_OPTIONS,
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
      return calculateStackedBarStats(this.stackedBarChartData);
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
    formatLabel(label) {
      return formatLabelUtil(label);
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
  },
};
</script>

<style scoped>
/* Add view-specific styles if needed */
</style>
