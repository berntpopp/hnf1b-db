<!-- src/views/AggregationsDashboard.vue -->
<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <v-sheet outlined>
          <v-card>
            <v-tabs
              v-model="tab"
              bg-color="primary"
            >
              <v-tab value="Donut Chart">
                Donut Chart
              </v-tab>
              <v-tab value="Stacked Bar Chart">
                Stacked Bar Chart
              </v-tab>
              <v-tab value="Time Plot">
                Time Plot
              </v-tab>
              <v-tab value="Protein Plot">
                Protein Plot
              </v-tab>
            </v-tabs>
            <v-card-text>
              <v-tabs-window v-model="tab">
                <!-- Donut Chart Tab -->
                <v-tabs-window-item value="Donut Chart">
                  <v-row class="pa-3">
                    <v-col
                      cols="12"
                      sm="6"
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
                      sm="6"
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
                  </v-row>
                  <component
                    :is="donutChartProps.content"
                    v-bind="donutChartProps.props"
                  />
                </v-tabs-window-item>
                <!-- Stacked Bar Chart Tab -->
                <v-tabs-window-item value="Stacked Bar Chart">
                  <component
                    :is="stackedBarChartProps.content"
                    v-bind="stackedBarChartProps.props"
                  />
                </v-tabs-window-item>
                <!-- Time Plot Tab -->
                <v-tabs-window-item value="Time Plot">
                  <component
                    :is="timePlotProps.content"
                    v-bind="timePlotProps.props"
                  />
                </v-tabs-window-item>
                <!-- Protein Plot Tab -->
                <v-tabs-window-item value="Protein Plot">
                  <component
                    :is="proteinPlotProps.content"
                    v-bind="proteinPlotProps.props"
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
import TimePlot from '@/components/analyses/TimePlot.vue';
import ProteinLinearPlot from '@/components/analyses/ProteinLinearPlot.vue';
import * as API from '@/api';

export default {
  name: 'AggregationsDashboard',
  components: {
    DonutChart,
    StackedBarChart,
    TimePlot,
    ProteinLinearPlot,
  },
  data() {
    return {
      tab: 'Donut Chart',
      chartData: {},
      stackedBarData: {},
      timePlotData: {},
      proteinPlotData: {}, // Will hold protein and variant data for protein plot.
      items: [
        {
          tab: 'Donut Chart',
          content: markRaw(DonutChart),
          props: { exportable: true, width: 600, height: 500 },
        },
        {
          tab: 'Stacked Bar Chart',
          content: markRaw(StackedBarChart),
          props: {
            width: 1000,
            height: 400,
            margin: { top: 10, right: 30, bottom: 150, left: 100 },
          },
        },
        {
          tab: 'Time Plot',
          content: markRaw(TimePlot),
          props: { width: 900, height: 400, margin: { top: 20, right: 50, bottom: 50, left: 70 } },
        },
        {
          tab: 'Protein Plot',
          content: markRaw(ProteinLinearPlot),
          props: { width: 900, height: 250 }, // adjust dimensions as desired.
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
            { label: 'Top HPO Terms', value: 'getPhenotypicFeaturesAggregation' },
          ],
        },
        {
          label: 'Diseases',
          aggregations: [
            { label: 'Disease Frequency', value: 'getDiseaseAggregation' },
          ],
        },
        {
          label: 'Variants',
          aggregations: [
            { label: 'Pathogenicity Classification', value: 'getVariantPathogenicity' },
            { label: 'Variant Types (SNV/CNV)', value: 'getVariantTypes' },
          ],
        },
        {
          label: 'Publications',
          aggregations: [
            { label: 'Publication Statistics', value: 'getPublicationsAggregation' },
          ],
        },
      ],
      selectedCategory: 'Phenopackets',
      selectedAggregation: 'getSexDistribution',
    };
  },
  computed: {
    donutChartProps() {
      return {
        content: this.items[0].content,
        props: { ...this.items[0].props, chartData: this.chartData },
      };
    },
    stackedBarChartProps() {
      return {
        content: this.items[1].content,
        props: { ...this.items[1].props, chartData: this.stackedBarData },
      };
    },
    timePlotProps() {
      return {
        content: this.items[2].content,
        props: { ...this.items[2].props, chartData: this.timePlotData },
      };
    },
    proteinPlotProps() {
      return {
        content: this.items[3].content,
        props: { ...this.items[3].props, chartData: this.proteinPlotData },
      };
    },
    selectedAggregations() {
      const category = this.categories.find((cat) => cat.label === this.selectedCategory);
      return category ? category.aggregations : [];
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
    tab(newTab) {
      if (newTab === 'Donut Chart') {
        this.fetchAggregationData();
      } else if (newTab === 'Stacked Bar Chart') {
        this.fetchStackedBarData();
      } else if (newTab === 'Time Plot') {
        this.fetchTimePlotData();
      } else if (newTab === 'Protein Plot') {
        this.fetchProteinPlotData();
      }
    },
  },
  mounted() {
    if (this.tab === 'Donut Chart') {
      this.fetchAggregationData();
    } else if (this.tab === 'Stacked Bar Chart') {
      this.fetchStackedBarData();
    } else if (this.tab === 'Time Plot') {
      this.fetchTimePlotData();
    } else if (this.tab === 'Protein Plot') {
      this.fetchProteinPlotData();
    }
  },
  methods: {
    fetchAggregationData() {
      const funcName = this.selectedAggregation;
      if (API[funcName] && typeof API[funcName] === 'function') {
        API[funcName]()
          .then((response) => {
            console.log('Donut chart data:', response.data);
            this.chartData = response.data;
          })
          .catch((error) => {
            console.error('Error fetching donut chart data:', error);
          });
      } else {
        console.error('API function not found:', funcName);
      }
    },
    fetchStackedBarData() {
      API.getPhenotypeDescribedCount()
        .then((response) => {
          console.log('Stacked bar chart data:', response.data);
          this.stackedBarData = response.data;
        })
        .catch((error) => {
          console.error('Error fetching stacked bar chart data:', error);
        });
    },
    fetchTimePlotData() {
      API.getPublicationsCumulativeCount()
        .then((response) => {
          console.log('Time plot data:', response.data);
          this.timePlotData = response.data;
        })
        .catch((error) => {
          console.error('Error fetching time plot data:', error);
        });
    },
    fetchProteinPlotData() {
      // Note: Protein structure data endpoint not yet implemented
      // For now, only fetch small variants
      API.getSmallVariants()
        .then((response) => {
          console.log('Small variants data:', response.data);
          // TODO: When protein endpoint is available, fetch protein data too
          this.proteinPlotData = { variants: response.data };
        })
        .catch((error) => {
          console.error('Error fetching protein plot data:', error);
        });
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
