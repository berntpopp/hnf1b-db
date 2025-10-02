<!-- src/views/PageIndividual.vue -->
<template>
  <v-container fluid>
    <v-row justify="center">
      <v-col cols="12">
        <v-sheet outlined>
          <!-- Loading overlay -->
          <v-overlay
            :absolute="absolute"
            :opacity="opacity"
            :value="loading"
            :color="color"
          >
            <v-progress-circular
              indeterminate
              color="primary"
            />
          </v-overlay>

          <!-- Individual & Variant Details Card -->
          <v-card
            class="mb-4"
            outlined
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="primary"
              >
                {{ icons.mdiAccount }}
              </v-icon>
              Individual Details
            </v-card-title>
            <v-card-text class="text-body-1">
              <v-row>
                <v-col
                  cols="12"
                  sm="6"
                >
                  <div><strong>ID:</strong> {{ individual.individual_id }}</div>
                  <div>
                    <strong>Sex:</strong>
                    <v-icon
                      small
                      color="primary"
                      class="mr-1"
                    >
                      {{ sex_symbol[(individual.Sex || 'unspecified').toLowerCase()] }}
                    </v-icon>
                    {{ individual.Sex }}
                  </div>
                  <div><strong>DupCheck:</strong> {{ individual.DupCheck }}</div>
                </v-col>
                <v-col
                  cols="12"
                  sm="6"
                >
                  <div><strong>Identifier:</strong> {{ individual.IndividualIdentifier }}</div>
                  <div><strong>Problematic:</strong> {{ individual.Problematic || 'None' }}</div>
                </v-col>
              </v-row>
              <v-divider class="my-2" />
              <div v-if="individual.variant">
                <v-card-subtitle class="text-h6">
                  <v-icon
                    left
                    color="deep-orange"
                  >
                    {{ icons.mdiNewspaperVariant }}
                  </v-icon>
                  Variant Details
                </v-card-subtitle>
                <v-row>
                  <v-col
                    cols="12"
                    sm="4"
                  >
                    <div><strong>Variant Ref:</strong> {{ individual.variant.variant_ref }}</div>
                  </v-col>
                  <v-col
                    cols="12"
                    sm="4"
                  >
                    <div>
                      <strong>Detection Method:</strong>
                      {{ individual.variant.detection_method }}
                    </div>
                  </v-col>
                  <v-col
                    cols="12"
                    sm="4"
                  >
                    <div><strong>Segregation:</strong> {{ individual.variant.segregation }}</div>
                  </v-col>
                </v-row>
              </div>
            </v-card-text>
          </v-card>

          <!-- Reports Card (Collapsible) -->
          <v-card
            outlined
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="primary"
              >
                mdi-file-document-outline
              </v-icon>
              Reports
            </v-card-title>
            <v-card-text>
              <v-expansion-panels
                focusable
                accordion
              >
                <v-expansion-panel
                  v-for="report in individual.reports"
                  :key="report.report_id"
                >
                  <v-expansion-panel-title>
                    <v-icon
                      start
                      color="deep-orange"
                    >
                      mdi-newspaper-variant-outline
                    </v-icon>
                    <span class="mr-2"><strong>{{ report.report_id }}</strong></span>
                    <small class="text-grey-darken-1">{{ report.report_date }}</small>
                  </v-expansion-panel-title>
                  <v-expansion-panel-text>
                    <v-list dense>
                      <v-list-item>
                        <v-list-item-title>
                          <div class="d-flex align-center">
                            <v-icon
                              color="primary"
                              class="mr-1"
                            >
                              mdi-calendar-check
                            </v-icon>
                            <span class="font-weight-bold">Reviewed on:</span>
                            <span class="ml-1">{{
                              report.review_date || report.report_review_date
                            }}</span>
                          </div>
                        </v-list-item-title>
                      </v-list-item>
                      <v-list-item>
                        <v-list-item-title>
                          <div class="d-flex align-center">
                            <v-icon
                              color="primary"
                              class="mr-1"
                            >
                              mdi-comment-text-outline
                            </v-icon>
                            <span class="font-weight-bold">Comment:</span>
                            <span class="ml-1">{{ report.comment }}</span>
                          </div>
                        </v-list-item-title>
                      </v-list-item>
                      <v-list-item>
                        <v-list-item-title>
                          <div class="d-flex align-center">
                            <v-icon
                              color="primary"
                              class="mr-1"
                            >
                              mdi-account-clock
                            </v-icon>
                            <span class="font-weight-bold">Age Reported:</span>
                            <span class="ml-1">{{ report.age_reported || report.report_age }}</span>
                          </div>
                        </v-list-item-title>
                      </v-list-item>
                      <v-list-item>
                        <v-list-item-title>
                          <div class="d-flex align-center">
                            <v-icon
                              color="primary"
                              class="mr-1"
                            >
                              mdi-gender-male-female
                            </v-icon>
                            <span class="font-weight-bold">Sex Reported:</span>
                            <span class="ml-1">
                              <v-icon
                                small
                                color="primary"
                                class="mr-1"
                              >
                                {{
                                  sex_symbol[
                                    (
                                      report.sex_reported ||
                                      individual.Sex ||
                                      'unspecified'
                                    ).toLowerCase()
                                  ]
                                }}
                              </v-icon>
                              {{ report.sex_reported || individual.Sex }}
                            </span>
                          </div>
                        </v-list-item-title>
                      </v-list-item>
                      <v-list-item>
                        <v-list-item-title>
                          <div class="d-flex align-center">
                            <v-icon
                              color="primary"
                              class="mr-1"
                            >
                              mdi-timer-outline
                            </v-icon>
                            <span class="font-weight-bold">Age Onset:</span>
                            <span class="ml-1">{{ report.age_onset || report.onset_age }}</span>
                          </div>
                        </v-list-item-title>
                      </v-list-item>
                      <v-list-item>
                        <v-list-item-title>
                          <div class="d-flex align-center">
                            <v-icon
                              color="primary"
                              class="mr-1"
                            >
                              mdi-account-group-outline
                            </v-icon>
                            <span class="font-weight-bold">Cohort:</span>
                            <span class="ml-1">
                              <v-chip
                                :color="
                                  cohort_style[
                                    (report.cohort || individual.cohort || 'grey').toLowerCase()
                                  ] || 'grey'
                                "
                                small
                              >
                                {{ report.cohort || individual.cohort }}
                              </v-chip>
                            </span>
                          </div>
                        </v-list-item-title>
                      </v-list-item>
                      <v-divider class="my-2" />
                      <v-list-item>
                        <v-list-item-title>
                          <div class="d-flex align-center">
                            <v-icon
                              color="primary"
                              class="mr-1"
                            >
                              mdi-tag-multiple-outline
                            </v-icon>
                            <span class="font-weight-bold">Phenotypes:</span>
                          </div>
                          <div class="chip-container">
                            <template
                              v-for="phenotype in normalizePhenotypes(report.phenotypes)"
                              :key="phenotype.phenotype_id"
                            >
                              <v-chip
                                class="phenotype-chip"
                                small
                                :color="
                                  reported_phenotype_color[phenotype.described.toLowerCase()] ||
                                    'grey'
                                "
                              >
                                <v-icon
                                  small
                                  left
                                >
                                  {{
                                    reported_phenotype_symbol[phenotype.described.toLowerCase()] ||
                                      'mdi-help-circle'
                                  }}
                                </v-icon>
                                {{ phenotype.name || phenotype.phenotype_name }}
                              </v-chip>
                            </template>
                          </div>
                        </v-list-item-title>
                      </v-list-item>
                    </v-list>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
            </v-card-text>
          </v-card>
        </v-sheet>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
import colorAndSymbolsMixin from '@/assets/js/mixins/colorAndSymbolsMixin.js';
import { getIndividuals } from '@/api';

export default {
  name: 'PageIndividual',
  mixins: [colorAndSymbolsMixin],
  data() {
    return {
      individual: {},
      absolute: true,
      opacity: 1,
      color: '#FFFFFF',
      loading: true,
      icons: {
        mdiAccount: 'mdi-account',
        mdiNewspaperVariant: 'mdi-newspaper-variant',
      },
      // Consistent fallback icons for sex:
      sex_symbol: {
        male: 'mdi-gender-male',
        female: 'mdi-gender-female',
        unspecified: 'mdi-gender-non-binary',
      },
      // Consistent styling for cohorts:
      cohort_style: {
        born: 'blue',
      },
      // Consistent color mapping for phenotypes:
      reported_phenotype_color: {
        yes: 'green',
        no: 'red',
        'not reported': 'orange',
      },
      reported_phenotype_symbol: {
        yes: 'mdi-check-circle',
        no: 'mdi-close-circle',
        'not reported': 'mdi-alert-circle',
      },
    };
  },
  created() {
    this.loadIndividualData();
  },
  methods: {
    async loadIndividualData() {
      this.loading = true;
      // Build the filter as a JSON string; the API expects: filter={"individual_id": "ind0001"}
      const filterParam = JSON.stringify({
        individual_id: this.$route.params.individual_id,
      });
      try {
        // Use page 1 & page_size 10 since we expect one record
        const response = await getIndividuals({ page: 1, page_size: 10, filter: filterParam });
        if (!response.data || response.data.length === 0) {
          this.$router.push('/PageNotFound');
        } else {
          this.individual = response.data[0];
        }
      } catch (e) {
        console.error(e);
      }
      this.loading = false;
    },
    /**
     * Normalize the phenotypes field.
     * If phenotypes is an object, convert it into an array.
     */
    normalizePhenotypes(phenotypes) {
      if (!phenotypes) return [];
      return Array.isArray(phenotypes) ? phenotypes : Object.values(phenotypes);
    },
  },
};
</script>

<style scoped>
.chip-container {
  display: flex;
  flex-wrap: wrap;
}
.phenotype-chip {
  font-size: 0.7rem;
  margin: 1px !important;
}
</style>
