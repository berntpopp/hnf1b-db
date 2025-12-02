<template>
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
              <th v-for="time in riskTableTimePoints" :key="time" class="text-center">
                {{ time }}y
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="group in survivalData.groups" :key="group.name">
              <td class="font-weight-medium">{{ group.name }}</td>
              <td v-for="time in riskTableTimePoints" :key="time" class="text-center">
                {{ getAtRiskCount(group, time) }}
              </td>
            </tr>
          </tbody>
        </v-table>
        <p class="text-caption text-grey mt-2">
          Number of patients still at risk (not yet experienced event or been censored) at each time
          point.
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
          Bonferroni-corrected p &lt; 0.05 considered statistically significant (marked with
          <v-icon size="x-small" color="success">mdi-check-circle</v-icon>). Correction: p ×
          {{ survivalData.statistical_tests?.length || 1 }} comparisons.
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
                <template #prepend>
                  <v-icon size="small" color="error">mdi-alert-circle</v-icon>
                </template>
                <v-list-item-title class="text-body-2"> Event Definition </v-list-item-title>
                <v-list-item-subtitle class="text-wrap">
                  {{ survivalData.metadata.event_definition }}
                </v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon size="small" color="info">mdi-clock-outline</v-icon>
                </template>
                <v-list-item-title class="text-body-2">Time Axis</v-list-item-title>
                <v-list-item-subtitle class="text-wrap">
                  {{ survivalData.metadata.time_axis }}
                </v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template #prepend>
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
            <h4 class="text-subtitle-1 font-weight-bold mb-2">Inclusion & Exclusion Criteria</h4>
            <v-list density="compact" class="bg-transparent">
              <v-list-item>
                <template #prepend>
                  <v-icon size="small" color="success">mdi-check-circle</v-icon>
                </template>
                <v-list-item-title class="text-body-2">Included</v-list-item-title>
                <v-list-item-subtitle class="text-wrap">
                  {{ survivalData.metadata.inclusion_criteria }}
                </v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template #prepend>
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
        <h4 class="text-subtitle-1 font-weight-bold mt-4 mb-2">Group Definitions</h4>
        <v-table density="compact">
          <thead>
            <tr>
              <th class="text-left" style="width: 150px">Group</th>
              <th class="text-left">Definition</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(definition, groupName) in survivalData.metadata.group_definitions"
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
</template>

<script>
export default {
  name: 'SurvivalDataPanels',
  props: {
    survivalData: {
      type: Object,
      default: null,
    },
  },
  computed: {
    riskTableTimePoints() {
      if (!this.survivalData?.groups?.length) return [];
      let maxTime = 0;
      this.survivalData.groups.forEach((group) => {
        group.survival_data.forEach((d) => {
          if (d.time > maxTime) maxTime = d.time;
        });
      });
      const step = Math.ceil(maxTime / 8);
      const points = [];
      for (let t = 0; t <= maxTime; t += step) {
        points.push(t);
      }
      return points;
    },
  },
  methods: {
    getAtRiskCount(group, time) {
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
