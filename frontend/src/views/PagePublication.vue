<!-- src/views/PagePublication.vue -->
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

          <!-- Publication Basic Details Card -->
          <v-card
            outlined
            class="mb-4"
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="cyan accent-2"
              >
                {{ icons.mdiBookOpenBlankVariant }}
              </v-icon>
              Publication:
              <v-chip
                color="cyan accent-2"
                class="ma-2"
              >
                {{ publication.publication_id }}
              </v-chip>
            </v-card-title>
            <v-card-text class="text-body-1">
              <v-list dense>
                <v-list-item>
                  <span class="font-weight-bold">PMID:</span>
                  <a
                    :href="'https://pubmed.ncbi.nlm.nih.gov/' + publication.pmid"
                    target="_blank"
                    class="ml-1"
                  >
                    {{ publication.pmid }}
                  </a>
                </v-list-item>
                <v-list-item>
                  <span class="font-weight-bold">DOI:</span>
                  <a
                    v-if="publication.doi && publication.doi !== 'nan'"
                    :href="'https://doi.org/' + publication.doi"
                    target="_blank"
                    class="ml-1"
                  >
                    {{ publication.doi }}
                  </a>
                  <span v-else>Not available</span>
                </v-list-item>
                <v-divider
                  inset
                  class="my-2"
                />
                <v-list-item v-if="publication.publication_entry_date">
                  <span class="font-weight-bold">Review Date:</span>
                  <span class="ml-1">{{ publication.publication_entry_date }}</span>
                </v-list-item>
                <v-list-item>
                  <span class="font-weight-bold">Title:</span>
                  <span class="ml-1">{{ publication.title || 'No title available' }}</span>
                </v-list-item>
                <v-list-item>
                  <span class="font-weight-bold">Abstract:</span>
                  <span class="ml-1">{{ publication.abstract || 'N/A' }}</span>
                </v-list-item>
                <v-list-item v-if="publication.publication_date">
                  <span class="font-weight-bold">Publication Date:</span>
                  <span class="ml-1">{{ publication.publication_date }}</span>
                </v-list-item>
                <v-list-item>
                  <span class="font-weight-bold">Journal:</span>
                  <span class="ml-1">{{ publication.journal || 'Not available' }}</span>
                </v-list-item>
                <v-list-item v-if="publication.authors && publication.authors.length">
                  <span class="font-weight-bold">Authors:</span>
                  <span class="ml-1">
                    {{
                      publication.authors
                        .map((author) => author.firstname + ' ' + author.lastname)
                        .join(', ')
                    }}
                  </span>
                </v-list-item>
              </v-list>
            </v-card-text>
          </v-card>

          <!-- Individuals in Publication Card -->
          <v-card
            v-if="individuals_in_publication_filter"
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
              Individuals in This Publication
            </v-card-title>
            <v-card-text>
              <TableIndividuals
                :show-filter-controls="false"
                :show-pagination-controls="false"
                :filter-input="individuals_in_publication_filter"
                header-label="Individuals"
                header-sub-label="described in this publication"
              />
            </v-card-text>
          </v-card>
        </v-sheet>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
import TableIndividuals from '@/components/tables/TableIndividuals.vue';
import colorAndSymbolsMixin from '@/assets/js/mixins/colorAndSymbolsMixin.js';
import { getPublications } from '@/api';

export default {
  name: 'PagePublication',
  components: {
    TableIndividuals,
  },
  mixins: [colorAndSymbolsMixin],
  data() {
    return {
      publication: {},
      absolute: true,
      opacity: 1,
      color: '#FFFFFF',
      loading: true,
      individuals_in_publication_filter: '',
      icons: {
        mdiBookOpenBlankVariant: 'mdi-book-open-blank-variant',
      },
    };
  },
  created() {
    this.loadPublicationData();
  },
  methods: {
    async loadPublicationData() {
      this.loading = true;
      // Build the filter as a JSON string; API expects: filter={"publication_id": <id>}
      const filterParam = JSON.stringify({
        publication_id: this.$route.params.publication_id,
      });
      try {
        const response = await getPublications({
          page: 1,
          page_size: 10,
          filter: filterParam,
        });
        if (!response.data || response.data.length === 0) {
          this.$router.push('/PageNotFound');
        } else {
          // We expect a single publication
          this.publication = response.data[0];
          // If the publication contains a reports property with individual IDs, build the filter string
          if (this.publication.reports && this.publication.reports.length) {
            const uniqueIds = [
              ...new Set(this.publication.reports.map((item) => item.individual_id)),
            ];
            this.individuals_in_publication_filter =
              'contains(individual_id,' + uniqueIds.join('|') + ')';
          }
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
/* Add any custom styles if needed */
</style>
