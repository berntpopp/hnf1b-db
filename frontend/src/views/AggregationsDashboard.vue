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
                  <StackedBarChart
                    :chart-data="stackedBarChartData"
                    :display-limit="stackedBarDisplayLimit"
                    :width="1000"
                    :height="600"
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
import * as API from '@/api';

export default {
  name: 'AggregationsDashboard',
  components: {
    DonutChart,
    StackedBarChart,
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
      displayLimitOptions: [
        { label: 'Top 10', value: 10 },
        { label: 'Top 20', value: 20 },
        { label: 'Top 30', value: 30 },
        { label: 'Top 50', value: 50 },
        { label: 'All Features', value: 9999 },
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
  },
};
</script>

<style scoped>
/* Add view-specific styles if needed */
</style>
