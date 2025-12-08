<!-- src/views/AggregationsDashboard.vue -->
<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <v-sheet outlined>
          <v-card>
            <v-tabs v-model="activeTabLabel" bg-color="primary">
              <v-tab v-for="tabDef in AGGREGATION_TABS" :key="tabDef.slug" :value="tabDef.label">
                {{ tabDef.label }}
              </v-tab>
            </v-tabs>
            <v-card-text>
              <v-tabs-window v-model="activeTabLabel">
                <!-- Donut Chart Tab -->
                <v-tabs-window-item value="Donut Chart">
                  <v-row class="pa-3">
                    <v-col
                      cols="12"
                      :sm="isVariantAggregation ? 6 : 12"
                      :md="isVariantAggregation ? 4 : 6"
                    >
                      <v-select
                        v-model="category"
                        :items="donutCategories"
                        item-title="label"
                        item-value="label"
                        label="Category"
                      />
                    </v-col>
                    <v-col
                      cols="12"
                      :sm="isVariantAggregation ? 6 : 12"
                      :md="isVariantAggregation ? 4 : 6"
                    >
                      <v-select
                        v-model="aggregation"
                        :items="selectedAggregations"
                        item-title="label"
                        item-value="value"
                        label="Aggregation"
                      />
                    </v-col>
                    <v-col v-if="isVariantAggregation" cols="12" sm="6" md="4">
                      <v-select
                        v-model="countMode"
                        :items="countModeOptions"
                        item-title="label"
                        item-value="value"
                        label="Count Mode"
                        hint="'All' counts variant instances (e.g., 864), 'Unique' counts distinct variants"
                        persistent-hint
                      />
                    </v-col>
                  </v-row>
                  <DonutChart
                    :chart-data="chartData"
                    :color-map="currentColorMap"
                    :exportable="true"
                    :width="600"
                    :height="500"
                  />
                </v-tabs-window-item>

                <!-- Stacked Bar Chart Tab -->
                <v-tabs-window-item value="Stacked Bar Chart">
                  <v-row class="pa-3">
                    <v-col cols="12" md="6">
                      <v-select
                        v-model="displayLimitValue"
                        :items="displayLimitOptions"
                        item-title="label"
                        item-value="value"
                        label="Number of Features to Display"
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
                    :display-limit="displayLimitValue"
                    :width="1200"
                    :height="800"
                  />
                </v-tabs-window-item>

                <!-- Publications Timeline Tab -->
                <v-tabs-window-item value="Publications Timeline">
                  <PublicationsTimelineChart v-model:mode="timelineMode" />
                </v-tabs-window-item>

                <!-- Variant Comparison Tab -->
                <v-tabs-window-item value="Variant Comparison">
                  <v-row class="pa-3">
                    <v-col cols="12" md="4">
                      <v-select
                        v-model="comparison"
                        :items="comparisonTypes"
                        item-title="label"
                        item-value="value"
                        label="Comparison Type"
                      />
                    </v-col>
                    <v-col cols="12" md="4">
                      <v-select
                        v-model="organSystem"
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
                    :comparison-type="comparison"
                    :organ-system-filter="organSystem"
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

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import DonutChart from '@/components/analyses/DonutChart.vue';
import StackedBarChart from '@/components/analyses/StackedBarChart.vue';
import PublicationsTimelineChart from '@/components/analyses/PublicationsTimelineChart.vue';
import VariantComparisonChart from '@/components/analyses/VariantComparisonChart.vue';
import KaplanMeierChart from '@/components/analyses/KaplanMeierChart.vue';
import DNADistanceAnalysis from '@/components/analyses/DNADistanceAnalysis.vue';
import SurvivalDataPanels from '@/components/analyses/SurvivalDataPanels.vue';
import * as API from '@/api';
import { useUrlState } from '@/composables/useUrlState';
import {
  AGGREGATION_TABS,
  DEFAULT_TAB,
  getTabLabel,
  getTabSlug,
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

// URL State Schema - defines all URL-synced parameters
const urlStateSchema = {
  // Tab selection
  tab: { default: DEFAULT_TAB, type: 'string' },
  // Donut chart options
  category: { default: 'Phenopackets', type: 'string' },
  aggregation: { default: 'getSexDistribution', type: 'string' },
  countMode: { default: 'all', type: 'string' },
  // Stacked bar options
  displayLimit: { default: 20, type: 'number' },
  // Publications timeline options
  timelineMode: { default: 'cumulative', type: 'string' },
  // Variant comparison options
  comparison: { default: 'truncating_vs_non_truncating', type: 'string' },
  organSystem: { default: 'all', type: 'string' },
  sortBy: { default: 'p_value', type: 'string' },
  // Survival options
  survivalComparison: { default: 'variant_type', type: 'string' },
  survivalEndpoint: { default: 'ckd_stage_3_plus', type: 'string' },
};

// Initialize URL state with schema
const {
  tab,
  category,
  aggregation,
  countMode,
  displayLimit,
  timelineMode,
  comparison,
  organSystem,
  sortBy,
  survivalComparison,
  survivalEndpoint,
} = useUrlState(urlStateSchema);

// Computed property to convert between URL slug and v-tabs label value
const activeTabLabel = computed({
  get: () => getTabLabel(tab.value),
  set: (label) => {
    tab.value = getTabSlug(label);
  },
});

// Alias for display limit (used in template)
const displayLimitValue = computed({
  get: () => displayLimit.value,
  set: (val) => {
    displayLimit.value = val;
  },
});

// Static configuration
const donutCategories = DONUT_CATEGORIES;
const countModeOptions = COUNT_MODE_OPTIONS;
const comparisonTypes = COMPARISON_TYPES;
const sortByOptions = SORT_BY_OPTIONS;
const organSystemOptions = ORGAN_SYSTEM_OPTIONS;
const survivalComparisonTypes = SURVIVAL_COMPARISON_TYPES;
const survivalEndpointOptions = SURVIVAL_ENDPOINT_OPTIONS;

// Reactive data
const chartData = ref({});
const stackedBarChartData = ref([]);
const comparisonData = ref(null);
const comparisonLoading = ref(false);
const comparisonError = ref(null);
const survivalData = ref(null);
const survivalLoading = ref(false);
const survivalError = ref(null);

// Computed properties
const selectedAggregations = computed(() => {
  const cat = donutCategories.find((c) => c.label === category.value);
  return cat ? cat.aggregations : [];
});

const isVariantAggregation = computed(() => {
  const cat = donutCategories.find((c) => c.label === category.value);
  const agg = cat?.aggregations.find((a) => a.value === aggregation.value);
  return agg?.supportsCountMode || false;
});

const currentColorMap = computed(() => {
  return AGGREGATION_COLOR_MAPS[aggregation.value] || null;
});

const displayLimitOptions = computed(() => {
  const totalFeatures = stackedBarChartData.value.length;
  return DISPLAY_LIMIT_OPTIONS.filter((option) => {
    if (option.threshold === 0) return true;
    return totalFeatures > option.threshold;
  });
});

const stackedBarStats = computed(() => {
  return calculateStackedBarStats(stackedBarChartData.value);
});

// Methods
function formatLabel(label) {
  return formatLabelUtil(label);
}

function fetchStackedBarData() {
  window.logService.debug('Fetching stacked bar chart data');

  API.getPhenotypicFeaturesAggregation()
    .then((response) => {
      window.logService.info('Stacked bar chart data loaded', {
        count: response.data?.length,
      });
      stackedBarChartData.value = response.data || [];
    })
    .catch((error) => {
      window.logService.error('Error fetching stacked bar chart data', {
        error: error.message,
      });
    });
}

function fetchAggregationData() {
  const cat = donutCategories.find((c) => c.label === category.value);
  const agg = cat?.aggregations.find((a) => a.value === aggregation.value);
  const funcName = aggregation.value;
  const params = { ...(agg?.params || {}) };

  if (agg?.supportsCountMode) {
    params.count_mode = countMode.value;
  }

  window.logService.debug('Fetching aggregation data', {
    category: category.value,
    aggregation: agg?.label,
    funcName: funcName,
    params: params,
    supportsCountMode: agg?.supportsCountMode || false,
  });

  if (API[funcName] && typeof API[funcName] === 'function') {
    API[funcName](params)
      .then((response) => {
        window.logService.info('Donut chart data loaded', {
          aggregation: agg?.title,
          count: response.data?.length,
        });

        window.logService.debug('Transforming aggregation data for chart', {
          rawDataCount: response.data?.length || 0,
          totalCount: response.data?.reduce((sum, item) => sum + item.count, 0) || 0,
          hasLimit: !!params.limit,
          limit: params.limit,
        });

        let data = response.data || [];
        const totalCount = data.reduce((sum, item) => sum + item.count, 0);

        let groupedCounts = [];

        if (params.limit && data.length > params.limit) {
          const topItems = data.slice(0, params.limit);
          const remainingItems = data.slice(params.limit);
          const othersCount = remainingItems.reduce((sum, item) => sum + item.count, 0);

          window.logService.debug('Applied client-side limit to data', {
            originalCount: data.length,
            limitedCount: topItems.length,
            othersCount: othersCount,
          });

          groupedCounts = topItems.map((item) => ({
            _id: formatLabel(item.label),
            count: item.count || 0,
          }));

          if (othersCount > 0) {
            groupedCounts.push({
              _id: 'Others',
              count: othersCount,
            });
          }
        } else {
          groupedCounts = data.map((item) => ({
            _id: formatLabel(item.label),
            count: item.count || 0,
          }));
        }

        chartData.value = {
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
}

async function fetchComparisonData() {
  comparisonLoading.value = true;
  comparisonError.value = null;

  window.logService.debug('Fetching variant comparison data', {
    comparisonType: comparison.value,
    sortBy: sortBy.value,
  });

  try {
    const response = await API.compareVariantTypes({
      comparison: comparison.value,
      limit: 100,
      min_prevalence: 0,
      sort_by: sortBy.value,
    });

    comparisonData.value = response.data;

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
    comparisonError.value =
      error.response?.data?.detail || 'Failed to load comparison data. Please try again.';
  } finally {
    comparisonLoading.value = false;
  }
}

async function fetchSurvivalData() {
  survivalLoading.value = true;
  survivalError.value = null;

  window.logService.debug('Fetching survival data', {
    comparison: survivalComparison.value,
    endpoint: survivalEndpoint.value,
  });

  try {
    const response = await API.getSurvivalData({
      comparison: survivalComparison.value,
      endpoint: survivalEndpoint.value,
    });

    survivalData.value = response.data;

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
    survivalError.value =
      error.response?.data?.detail || 'Failed to load survival data. Please try again.';
  } finally {
    survivalLoading.value = false;
  }
}

// Watchers
watch(aggregation, () => {
  fetchAggregationData();
});

watch(category, () => {
  const aggregations = selectedAggregations.value;
  if (aggregations.length > 0 && !aggregations.find((a) => a.value === aggregation.value)) {
    aggregation.value = aggregations[0].value;
  }
  fetchAggregationData();
});

watch(countMode, () => {
  fetchAggregationData();
});

watch(displayLimit, () => {
  // Stacked bar uses displayLimit reactively via prop, no need to refetch
});

watch(tab, (newTab) => {
  // Auto-fetch data when switching to specific tabs
  if (newTab === 'variant-comparison' && !comparisonData.value) {
    fetchComparisonData();
  }
  if (newTab === 'survival' && !survivalData.value) {
    fetchSurvivalData();
  }
});

watch([comparison, sortBy], () => {
  if (tab.value === 'variant-comparison') {
    fetchComparisonData();
  }
});

watch([survivalComparison, survivalEndpoint], () => {
  if (tab.value === 'survival') {
    fetchSurvivalData();
  }
});

// Lifecycle
onMounted(() => {
  fetchAggregationData();
  fetchStackedBarData();

  // If starting on a tab that needs data, fetch it
  if (tab.value === 'variant-comparison') {
    fetchComparisonData();
  }
  if (tab.value === 'survival') {
    fetchSurvivalData();
  }
});
</script>

<style scoped>
/* Add view-specific styles if needed */
</style>
