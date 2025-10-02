<!-- src/views/PageVariant.vue -->
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

          <!-- Variant Basic Details Card -->
          <v-card
            outlined
            class="mb-4"
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="pink darken-2"
              >
                mdi-dna
              </v-icon>
              Variant Details
              <v-chip
                color="pink lighten-4"
                class="ma-2"
              >
                {{ variant.variant_id }}
              </v-chip>
            </v-card-title>
            <v-card-text class="text-body-1">
              <v-row>
                <v-col
                  cols="12"
                  sm="6"
                >
                  <div><strong>Type:</strong> {{ variant.variant_type }}</div>
                  <div><strong>HG19:</strong> {{ variant.hg19 }}</div>
                  <div><strong>HG19 Info:</strong> {{ variant.hg19_INFO || 'N/A' }}</div>
                </v-col>
                <v-col
                  cols="12"
                  sm="6"
                >
                  <div><strong>HG38:</strong> {{ variant.hg38 }}</div>
                  <div><strong>HG38 Info:</strong> {{ variant.hg38_INFO || 'N/A' }}</div>
                  <div>
                    <strong>Individuals Count:</strong>
                    {{ variant.individual_ids ? variant.individual_ids.length : 'N/A' }}
                  </div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- Classification Details Card -->
          <v-card
            v-if="variant.classifications && variant.classifications.length"
            outlined
            class="mb-4"
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="deep-purple"
              >
                mdi-clipboard-check-outline
              </v-icon>
              Classification
            </v-card-title>
            <v-card-text>
              <v-list dense>
                <v-list-item
                  v-for="(cl, index) in variant.classifications"
                  :key="index"
                >
                  <v-list-item-title>
                    <div class="d-flex align-center">
                      <v-icon
                        color="deep-purple"
                        class="mr-1"
                      >
                        mdi-check-circle-outline
                      </v-icon>
                      <span class="font-weight-bold">Verdict:</span>
                      <span class="ml-1">{{ cl.verdict }}</span>
                    </div>
                    <div class="d-flex align-center">
                      <v-icon
                        color="deep-purple"
                        class="mr-1"
                      >
                        mdi-calendar-clock
                      </v-icon>
                      <span class="font-weight-bold">Date:</span>
                      <span class="ml-1">{{ cl.classification_date }}</span>
                    </div>
                    <div class="d-flex align-center">
                      <v-icon
                        color="deep-purple"
                        class="mr-1"
                      >
                        mdi-format-list-bulleted
                      </v-icon>
                      <span class="font-weight-bold">Criteria:</span>
                      <span class="ml-1">{{ cl.criteria }}</span>
                    </div>
                    <div
                      v-if="cl.comment"
                      class="d-flex align-center"
                    >
                      <v-icon
                        color="deep-purple"
                        class="mr-1"
                      >
                        mdi-comment-alert-outline
                      </v-icon>
                      <span class="font-weight-bold">Comment:</span>
                      <span class="ml-1">{{ cl.comment }}</span>
                    </div>
                  </v-list-item-title>
                </v-list-item>
              </v-list>
            </v-card-text>
          </v-card>

          <!-- Annotations Card (Collapsible) -->
          <v-card
            v-if="variant.annotations && variant.annotations.length"
            outlined
            class="mb-4"
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="teal"
              >
                mdi-note-text-outline
              </v-icon>
              Annotations
            </v-card-title>
            <v-card-text>
              <v-expansion-panels accordion>
                <v-expansion-panel
                  v-for="(ann, index) in variant.annotations"
                  :key="index"
                >
                  <v-expansion-panel-title>
                    <v-icon
                      start
                      color="teal"
                    >
                      mdi-file-document-outline
                    </v-icon>
                    <span class="font-weight-bold">{{ ann.transcript }}</span>
                    <small class="text-grey-darken-1 ml-2">({{ ann.annotation_date }})</small>
                  </v-expansion-panel-title>
                  <v-expansion-panel-text>
                    <v-list dense>
                      <v-list-item>
                        <v-list-item-title>
                          <div class="d-flex align-center">
                            <v-icon
                              color="teal"
                              class="mr-1"
                            >
                              mdi-code-tags
                            </v-icon>
                            <span class="font-weight-bold">cDNA:</span>
                            <span class="ml-1">{{ ann.c_dot || 'N/A' }}</span>
                          </div>
                        </v-list-item-title>
                      </v-list-item>
                      <v-list-item>
                        <v-list-item-title>
                          <div class="d-flex align-center">
                            <v-icon
                              color="teal"
                              class="mr-1"
                            >
                              mdi-cube-outline
                            </v-icon>
                            <span class="font-weight-bold">Protein:</span>
                            <span class="ml-1">{{ ann.p_dot || 'N/A' }}</span>
                          </div>
                        </v-list-item-title>
                      </v-list-item>
                    </v-list>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
            </v-card-text>
          </v-card>

          <!-- Reported Data Card -->
          <v-card
            v-if="variant.reported && variant.reported.length"
            outlined
            class="mb-4"
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="orange"
              >
                mdi-alert-circle-outline
              </v-icon>
              Reported Variants
            </v-card-title>
            <v-card-text>
              <v-list dense>
                <v-list-item
                  v-for="(rep, idx) in variant.reported"
                  :key="idx"
                >
                  <template #prepend>
                    <v-icon color="orange">
                      mdi-file-document-outline
                    </v-icon>
                  </template>
                  <v-list-item-title class="d-flex align-center">
                    <span class="font-weight-bold">Reported:</span>
                    <span class="ml-1">{{ rep.variant_reported }}</span>
                  </v-list-item-title>
                  <v-list-item-subtitle>
                    <div class="d-flex align-center">
                      <v-icon
                        color="orange"
                        class="mr-1"
                      >
                        mdi-book-open-page-variant
                      </v-icon>
                      <span class="font-weight-bold">Publication:</span>
                      <span class="ml-1">{{ rep.publication_ref }}</span>
                    </div>
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-card-text>
          </v-card>

          <!-- Protein Linear Plot Card -->
          <v-card
            outlined
            class="mb-4"
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="indigo"
              >
                mdi-chart-line
              </v-icon>
              Protein Linear Plot
            </v-card-title>
            <v-card-text>
              <ProteinLinearPlot
                :show_controls="false"
                :variant_filter="'equals(variant_id,' + variant.variant_id + ')'"
              />
            </v-card-text>
          </v-card>

          <!-- Individuals Carrying This Variant Card -->
          <v-card
            outlined
            class="mb-4"
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="primary"
              >
                mdi-account-multiple-outline
              </v-icon>
              Individuals Carrying This Variant
            </v-card-title>
            <v-card-text>
              <TableIndividuals
                :show-filter-controls="false"
                :show-pagination-controls="false"
                :filter-input="individuals_with_variant_filter"
                header-label="Individuals"
                header-sub-label="carrying this variant"
              />
            </v-card-text>
          </v-card>
        </v-sheet>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
import ProteinLinearPlot from '@/components/analyses/ProteinLinearPlot.vue';
import TableIndividuals from '@/components/tables/TableIndividuals.vue';
import colorAndSymbolsMixin from '@/assets/js/mixins/colorAndSymbolsMixin.js';
import { getVariants } from '@/api';

export default {
  name: 'PageVariant',
  components: {
    ProteinLinearPlot,
    TableIndividuals,
  },
  mixins: [colorAndSymbolsMixin],
  data() {
    return {
      variant: {},
      absolute: true,
      opacity: 1,
      color: '#FFFFFF',
      loading: true,
      individuals_with_variant: [],
      individuals_with_variant_filter: '',
      icons: {
        mdiDna: 'mdi-dna',
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
      // Consistent color mapping for phenotype:
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
    this.loadVariantData();
  },
  methods: {
    async loadVariantData() {
      this.loading = true;
      // Build filter as a JSON string; API expects filter={"variant_id": "varXXXX"}
      const filterParam = JSON.stringify({
        variant_id: this.$route.params.variant_id,
      });
      try {
        const response = await getVariants({
          page: 1,
          page_size: 10,
          filter: filterParam,
        });
        if (!response.data || response.data.length === 0) {
          this.$router.push('/PageNotFound');
        } else {
          this.variant = response.data[0];
          // Build filter string for TableIndividuals based on variant.individual_ids if defined
          this.individuals_with_variant_filter =
            this.variant.individual_ids && this.variant.individual_ids.length
              ? 'contains(individual_id,' + this.variant.individual_ids.join('|') + ')'
              : '';
        }
      } catch (e) {
        console.error(e);
      }
      this.loading = false;
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
