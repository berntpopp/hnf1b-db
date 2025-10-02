<template>
  <v-container fluid>
    <v-sheet outlined>
      <!-- Overlay spinner while loading -->
      <v-overlay
        :absolute="true"
        :opacity="1"
        :value="loading"
        color="#FFFFFF"
      >
        <v-progress-circular
          indeterminate
          color="primary"
        />
      </v-overlay>

      <!-- Table header -->
      <div class="text-lg-h6">
        {{ headerLabel }}
      </div>
      <p class="text-justify">
        {{ headerSubLabel }}
      </p>

      <!-- The expandable data table -->
      <v-data-table
        dense
        :items="transformedIndividuals"
        :headers="tableHeaders"
        item-key="individual_id"
        show-expand
        :single-expand="true"
        class="elevation-1"
      >
        <!-- Expand icon slot using Vuetify 3's toggle property -->
        <template #item.data-table-expand="{ toggle, isExpanded }">
          <v-btn
            icon
            aria-label="Expand report table"
            :class="{ 'v-data-table__expand-icon--active': isExpanded }"
            @click="toggle()"
          >
            <v-icon>{{ icons.mdiChevronDown }}</v-icon>
          </v-btn>
        </template>

        <!-- Individual ID cell -->
        <template #item.individual_id="{ item }">
          <v-chip
            color="lime lighten-2"
            class="ma-2"
            small
            link
            variant="flat"
            :prepend-icon="icons.mdiAccount"
            :to="'/individuals/' + item.individual_id"
          >
            {{ item.individual_id }}
          </v-chip>
        </template>

        <!-- Sex cell with tooltip and icon -->
        <template #item.Sex="{ item }">
          <v-icon right>
            {{ sex_symbol[item.Sex] }}
          </v-icon>
        </template>

        <!-- Expanded row: display report details -->
        <template #expanded-item="{ headers, item }">
          <td :colspan="headers.length">
            <v-data-table
              dense
              :items="item.reportsArray"
              :headers="reportHeaders"
              class="elevation-1"
              hide-default-footer
              disable-pagination
              disable-filtering
              item-key="report_id"
            >
              <!-- Report ID as a chip with link -->
              <template #item.report_id="{ item: report }">
                <v-chip
                  color="deep-orange lighten-2"
                  class="ma-2"
                  small
                  link
                  :to="'/report/' + report.report_id"
                >
                  {{ report.report_id }}
                  <v-icon right>
                    {{ icons.mdiNewspaperVariant }}
                  </v-icon>
                </v-chip>
              </template>

              <!-- Cohort cell as a chip -->
              <template #item.cohort="{ item: report }">
                <v-chip
                  :color="cohortColor(report.cohort)"
                  class="ma-2"
                  small
                >
                  {{ report.cohort }}
                </v-chip>
              </template>

              <!-- Phenotypes cell: display each phenotype as a chip -->
              <template #item.phenotypes="{ item: report }">
                <div class="d-flex flex-wrap">
                  <v-chip
                    v-for="phenotype in report.phenotypesArray"
                    :key="phenotype.phenotype_id"
                    :color="reportedPhenotypeColor(phenotype.described)"
                    small
                    class="ma-1"
                  >
                    <v-icon
                      left
                      small
                    >
                      {{ reportedPhenotypeSymbol(phenotype.described) }}
                    </v-icon>
                    {{ phenotype.name }}
                  </v-chip>
                </div>
              </template>
            </v-data-table>
          </td>
        </template>
      </v-data-table>
    </v-sheet>
  </v-container>
</template>

<script>
import colorAndSymbolsMixin from '@/assets/js/mixins/colorAndSymbolsMixin.js';

export default {
  name: 'TableIndividuals',
  mixins: [colorAndSymbolsMixin],
  props: {
    headerLabel: {
      type: String,
      default: 'Individuals Table',
    },
    headerSubLabel: {
      type: String,
      default: 'Search and filter the reviewed individuals in a tabular view.',
    },
    // Array of individuals to display; do not mutate this prop directly.
    individuals: {
      type: Array,
      default: () => [],
    },
    // Loading flag for the table.
    loading: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      // Headers for the main individuals table.
      tableHeaders: [
        { title: 'Individual', value: 'individual_id' },
        { title: 'Sex', value: 'Sex' },
      ],
      // Headers for the nested reports table.
      reportHeaders: [
        { title: 'Report', value: 'report_id' },
        { title: 'Review Date', value: 'review_date' },
        { title: 'Cohort', value: 'cohort' },
        { title: 'Comment', value: 'comment' },
        { title: 'Phenotypes', value: 'phenotypes' },
      ],
    };
  },
  computed: {
    // Return a new array of individuals with an added 'reportsArray'
    transformedIndividuals() {
      return this.individuals.map((individual) => {
        let reportsArray = [];
        if (Array.isArray(individual.reports)) {
          reportsArray = individual.reports.map((report) => {
            let phenotypesArray = [];
            if (report.phenotypes && !Array.isArray(report.phenotypes)) {
              phenotypesArray = Object.values(report.phenotypes);
            } else {
              phenotypesArray = report.phenotypes || [];
            }
            return { ...report, phenotypesArray };
          });
        }
        return { ...individual, reportsArray };
      });
    },
  },
  methods: {
    // Fallback definitions if not provided by the mixin.
    sexSymbol(sex) {
      if (!sex) return 'mdi-help-circle';
      const lower = sex.toLowerCase();
      if (lower === 'female') return 'mdi-gender-female';
      if (lower === 'male') return 'mdi-gender-male';
      return 'mdi-gender-non-binary';
    },
    reportedPhenotypeColor(described) {
      if (!described) return 'grey';
      const lower = described.toLowerCase();
      if (lower === 'yes') return 'green';
      if (lower === 'no') return 'red';
      if (lower === 'not reported') return 'orange';
      return 'blue';
    },
    reportedPhenotypeSymbol(described) {
      if (!described) return 'mdi-help-circle';
      const lower = described.toLowerCase();
      if (lower === 'yes') return 'mdi-check-circle';
      if (lower === 'no') return 'mdi-close-circle';
      if (lower === 'not reported') return 'mdi-alert-circle';
      return 'mdi-help-circle';
    },
    cohortColor(cohort) {
      if (!cohort) return 'grey';
      return cohort.toLowerCase() === 'born' ? 'blue' : 'grey';
    },
  },
};
</script>

<style scoped>
/* Rotate the expand icon when active */
.v-data-table__expand-icon--active {
  transform: rotate(180deg);
}
</style>
