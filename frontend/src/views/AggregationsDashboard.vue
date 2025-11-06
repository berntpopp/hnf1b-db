<!-- src/views/AggregationsDashboard.vue -->
<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <v-sheet outlined>
          <v-card>
            <v-tabs v-model="tab" bg-color="primary">
              <v-tab value="Donut Chart"> Donut Chart </v-tab>
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
                        :items="categories"
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
import * as API from '@/api';

export default {
  name: 'AggregationsDashboard',
  components: {
    DonutChart,
  },
  data() {
    return {
      tab: 'Donut Chart',
      chartData: {},
      items: [
        {
          tab: 'Donut Chart',
          content: markRaw(DonutChart),
          props: { exportable: true, width: 600, height: 500 },
        },
      ],
      categories: [
        {
          label: 'Phenopackets',
          aggregations: [
            { label: 'Sex Distribution', value: 'getSexDistribution' },
            { label: 'Age of Onset', value: 'getAgeOfOnsetAggregation' },
            { label: 'Kidney Disease Stages', value: 'getKidneyStages' },
          ],
        },
        {
          label: 'Phenotypic Features',
          aggregations: [
            {
              label: 'Top 20 HPO Terms',
              value: 'getPhenotypicFeaturesAggregation',
              params: { limit: 20 },
            },
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
      const category = this.categories.find((cat) => cat.label === this.selectedCategory);
      return category ? category.aggregations : [];
    },
    isVariantAggregation() {
      const category = this.categories.find((cat) => cat.label === this.selectedCategory);
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
  },
  methods: {
    fetchAggregationData() {
      const category = this.categories.find((cat) => cat.label === this.selectedCategory);
      const aggregation = category?.aggregations.find(
        (agg) => agg.value === this.selectedAggregation
      );
      const funcName = this.selectedAggregation;
      const params = { ...(aggregation?.params || {}) };

      // Add count_mode parameter if this is a variant aggregation
      if (aggregation?.supportsCountMode) {
        params.count_mode = this.variantCountMode;
      }

      if (API[funcName] && typeof API[funcName] === 'function') {
        API[funcName](params)
          .then((response) => {
            console.log('Donut chart data:', response.data);

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
            console.error('Error fetching donut chart data:', error);
          });
      } else {
        console.error('API function not found:', funcName);
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
