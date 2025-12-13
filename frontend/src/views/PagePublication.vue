<!-- src/views/PagePublication.vue -->
<!--
  Publication Detail View with server-side pagination for individuals.

  Features:
  - Hero section with publication metadata and stats chips
  - Backend API integration (getPublicationMetadata)
  - Tabs for Overview and Individuals
  - Server-side pagination for individuals table
  - External links to PubMed and DOI
  - Internal navigation to phenopacket details
-->
<template>
  <div class="publication-container">
    <!-- HERO SECTION - Compact Publication Header -->
    <section class="hero-section py-2 px-4 mb-2">
      <v-container>
        <v-row justify="center" align="center">
          <v-col cols="12" xl="10">
            <!-- Compact Header with Breadcrumbs -->
            <div class="d-flex align-center flex-wrap gap-2 mb-2">
              <v-btn
                icon="mdi-arrow-left"
                variant="text"
                size="small"
                aria-label="Go back to publications list"
                @click="$router.push('/publications')"
              />
              <v-breadcrumbs :items="breadcrumbs" class="pa-0 flex-grow-0" density="compact" />
            </div>

            <!-- Title Row with Inline Stats Chips -->
            <div class="d-flex flex-wrap align-center gap-3">
              <v-icon color="orange-darken-2" size="large" aria-hidden="true">
                mdi-book-open-variant
              </v-icon>
              <div class="flex-grow-1">
                <div class="d-flex flex-wrap align-center gap-2">
                  <h1 class="text-h6 font-weight-bold text-orange-darken-2 ma-0">
                    Publication Details
                  </h1>
                  <!-- Loading skeleton -->
                  <template v-if="loading">
                    <v-skeleton-loader type="chip" width="100" class="ma-0" />
                    <v-skeleton-loader type="chip" width="80" class="ma-0" />
                  </template>
                  <!-- Loaded: Inline Stats Chips -->
                  <template v-else-if="publication">
                    <v-chip
                      :href="`https://pubmed.ncbi.nlm.nih.gov/${publicationId}`"
                      color="orange-lighten-3"
                      size="small"
                      variant="flat"
                      target="_blank"
                      link
                      class="font-weight-medium"
                    >
                      <v-icon start size="x-small">mdi-book-open-variant</v-icon>
                      PMID: {{ publicationId }}
                      <v-icon end size="x-small">mdi-open-in-new</v-icon>
                    </v-chip>
                    <v-chip
                      v-if="publication.year"
                      color="grey-lighten-2"
                      size="small"
                      variant="flat"
                    >
                      <v-icon start size="x-small">mdi-calendar</v-icon>
                      {{ publication.year }}
                    </v-chip>
                    <v-chip color="green-lighten-3" size="small" variant="flat">
                      <v-icon start size="x-small">mdi-account-multiple</v-icon>
                      {{ pagination.totalRecords }} Individual{{
                        pagination.totalRecords === 1 ? '' : 's'
                      }}
                    </v-chip>
                  </template>
                </div>
              </div>
            </div>
          </v-col>
        </v-row>
      </v-container>
    </section>

    <!-- MAIN CONTENT -->
    <v-container class="pb-12">
      <v-row justify="center">
        <v-col cols="12" xl="10">
          <!-- Error State -->
          <v-alert v-if="error" type="error" variant="tonal" prominent class="mb-6">
            <v-alert-title>Error Loading Publication</v-alert-title>
            {{ error }}
            <template #append>
              <v-btn color="error" variant="text" @click="$router.push('/publications')">
                Back to Publications
              </v-btn>
            </template>
          </v-alert>

          <!-- Main Content Card -->
          <v-card v-else-if="publication" variant="outlined" class="border-opacity-12" rounded="lg">
            <!-- Action Bar -->
            <div class="d-flex align-center flex-wrap px-4 py-2 bg-grey-lighten-4 border-bottom">
              <v-icon color="orange-darken-2" class="mr-2" aria-hidden="true">
                mdi-file-document
              </v-icon>
              <span class="text-h6 font-weight-medium">{{ truncateTitle(publication.title) }}</span>
              <v-spacer />
              <v-chip
                v-if="publication.doi"
                :href="`https://doi.org/${publication.doi}`"
                color="blue-lighten-3"
                size="small"
                variant="flat"
                target="_blank"
                link
                class="mr-2"
              >
                <v-icon start size="x-small">mdi-link-variant</v-icon>
                DOI
                <v-icon end size="x-small">mdi-open-in-new</v-icon>
              </v-chip>
            </div>

            <!-- Tabs for different views -->
            <v-tabs v-model="activeTab" color="orange-darken-2" align-tabs="start" class="px-4">
              <v-tab value="overview">
                <v-icon start size="small">mdi-information</v-icon>
                Overview
              </v-tab>
              <v-tab value="individuals">
                <v-icon start size="small">mdi-account-multiple</v-icon>
                Individuals ({{ pagination.totalRecords }})
              </v-tab>
            </v-tabs>

            <v-divider />

            <v-tabs-window v-model="activeTab">
              <!-- Overview Tab -->
              <v-tabs-window-item value="overview">
                <v-card-text class="pa-6">
                  <v-row>
                    <!-- Publication Metadata -->
                    <v-col cols="12">
                      <div class="mb-4">
                        <div class="text-subtitle-2 text-grey-darken-1 mb-1">Title</div>
                        <div class="text-body-1 font-weight-medium">
                          {{ publication.title || 'Title not available' }}
                        </div>
                      </div>

                      <div v-if="publication.authors" class="mb-4">
                        <div class="text-subtitle-2 text-grey-darken-1 mb-1">Authors</div>
                        <div class="text-body-2">{{ formatAuthors(publication.authors) }}</div>
                      </div>

                      <div v-if="publication.journal" class="mb-4">
                        <div class="text-subtitle-2 text-grey-darken-1 mb-1">Journal</div>
                        <div class="text-body-2 font-italic">{{ publication.journal }}</div>
                      </div>

                      <v-row>
                        <v-col v-if="publication.year" cols="auto">
                          <div class="text-subtitle-2 text-grey-darken-1 mb-1">Year</div>
                          <v-chip color="grey-lighten-2" size="small" variant="flat">
                            {{ publication.year }}
                          </v-chip>
                        </v-col>
                        <v-col v-if="publication.doi" cols="auto">
                          <div class="text-subtitle-2 text-grey-darken-1 mb-1">DOI</div>
                          <v-chip
                            :href="`https://doi.org/${publication.doi}`"
                            color="blue-lighten-3"
                            size="small"
                            variant="flat"
                            target="_blank"
                            link
                          >
                            {{ publication.doi }}
                            <v-icon end size="x-small">mdi-open-in-new</v-icon>
                          </v-chip>
                        </v-col>
                        <v-col cols="auto">
                          <div class="text-subtitle-2 text-grey-darken-1 mb-1">PubMed</div>
                          <v-chip
                            :href="`https://pubmed.ncbi.nlm.nih.gov/${publicationId}`"
                            color="orange-lighten-3"
                            size="small"
                            variant="flat"
                            target="_blank"
                            link
                          >
                            PMID: {{ publicationId }}
                            <v-icon end size="x-small">mdi-open-in-new</v-icon>
                          </v-chip>
                        </v-col>
                      </v-row>

                      <!-- Data Summary Card -->
                      <v-card variant="tonal" color="green-lighten-5" class="mt-6">
                        <v-card-text>
                          <div class="d-flex align-center gap-2">
                            <v-icon color="green-darken-2">mdi-account-multiple</v-icon>
                            <span class="text-body-1 font-weight-medium">
                              {{ pagination.totalRecords }} Individual{{
                                pagination.totalRecords === 1 ? '' : 's'
                              }}
                              in Registry
                            </span>
                          </div>
                          <div class="text-body-2 text-grey-darken-1 mt-2">
                            This publication has contributed
                            {{ pagination.totalRecords }} phenopacket record{{
                              pagination.totalRecords === 1 ? '' : 's'
                            }}
                            to the HNF1B database.
                          </div>
                          <v-btn
                            color="green-darken-2"
                            variant="tonal"
                            size="small"
                            class="mt-3"
                            @click="activeTab = 'individuals'"
                          >
                            <v-icon start>mdi-arrow-right</v-icon>
                            View Individuals
                          </v-btn>
                        </v-card-text>
                      </v-card>
                    </v-col>
                  </v-row>
                </v-card-text>
              </v-tabs-window-item>

              <!-- Individuals Tab -->
              <v-tabs-window-item value="individuals">
                <v-card-text class="pa-4">
                  <!-- Individuals Table with Server-Side Pagination -->
                  <AppDataTable
                    v-model:options="tableOptions"
                    :headers="headers"
                    :items="phenopackets"
                    :loading="phenopacketsLoading"
                    :items-length="pagination.totalRecords"
                    :custom-sort="customSort"
                    hide-default-footer
                    row-class="clickable-row"
                    @update:options="onOptionsUpdate"
                    @click:row="handleRowClick"
                  >
                    <!-- Pagination controls above table -->
                    <template #top>
                      <AppPagination
                        :current-count="phenopackets.length"
                        :current-page="pagination.currentPage"
                        :page-size="pagination.pageSize"
                        :total-pages="pagination.totalPages"
                        :total-records="pagination.totalRecords"
                        :items-per-page-options="itemsPerPageOptions"
                        @go-to-page="goToPage"
                        @update:page-size="onPageSizeChange"
                      />
                    </template>

                    <!-- Phenopacket ID as clickable chip -->
                    <template #item.id="{ item }">
                      <v-chip
                        :to="`/phenopackets/${item.id}`"
                        color="teal-lighten-3"
                        size="small"
                        variant="flat"
                        link
                      >
                        <v-icon start size="x-small">mdi-file-document</v-icon>
                        {{ item.id }}
                      </v-chip>
                    </template>

                    <!-- Subject ID -->
                    <template #item.subject_id="{ item }">
                      <span class="text-body-2">{{ item.subject?.id || 'N/A' }}</span>
                    </template>

                    <!-- Subject Sex with color coding -->
                    <template #item.subject_sex="{ item }">
                      <v-chip
                        v-if="item.subject?.sex"
                        :color="getSexColor(item.subject.sex)"
                        size="x-small"
                        variant="flat"
                      >
                        <v-icon start size="x-small">{{ getSexIcon(item.subject.sex) }}</v-icon>
                        {{ formatSex(item.subject.sex) }}
                      </v-chip>
                      <span v-else class="text-body-2 text-medium-emphasis">-</span>
                    </template>

                    <!-- Phenotypic Features Count -->
                    <template #item.features_count="{ item }">
                      <v-chip color="purple-lighten-3" size="x-small" variant="flat">
                        {{ item.phenotypicFeatures?.length || 0 }}
                      </v-chip>
                    </template>

                    <!-- Variants Count -->
                    <template #item.variants_count="{ item }">
                      <v-chip
                        v-if="getVariantCount(item) > 0"
                        color="red-lighten-3"
                        size="x-small"
                        variant="flat"
                      >
                        {{ getVariantCount(item) }}
                      </v-chip>
                      <span v-else class="text-body-2 text-medium-emphasis">-</span>
                    </template>

                    <!-- Pagination controls below table -->
                    <template #bottom>
                      <AppPagination
                        :current-count="phenopackets.length"
                        :current-page="pagination.currentPage"
                        :page-size="pagination.pageSize"
                        :total-pages="pagination.totalPages"
                        :total-records="pagination.totalRecords"
                        :items-per-page-options="itemsPerPageOptions"
                        @go-to-page="goToPage"
                        @update:page-size="onPageSizeChange"
                      />
                    </template>

                    <template #no-data>
                      <v-alert type="info" variant="tonal" density="compact">
                        No individuals found for this publication.
                      </v-alert>
                    </template>
                  </AppDataTable>
                </v-card-text>
              </v-tabs-window-item>
            </v-tabs-window>
          </v-card>

          <!-- Loading State -->
          <v-card v-else-if="loading" variant="outlined" class="border-opacity-12" rounded="lg">
            <v-card-text class="text-center py-12">
              <v-progress-circular indeterminate color="orange-darken-2" size="64" />
              <div class="mt-4 text-grey-darken-1">Loading publication...</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<script>
import { ref, computed } from 'vue';
import { useRoute } from 'vue-router';
import { getPublicationMetadata, getPhenopacketsByPublication } from '@/api';
import { buildSortParameter } from '@/utils/pagination';
import AppDataTable from '@/components/common/AppDataTable.vue';
import AppPagination from '@/components/common/AppPagination.vue';
import {
  usePublicationSeo,
  usePublicationStructuredData,
  useBreadcrumbStructuredData,
} from '@/composables/useSeoMeta';

export default {
  name: 'PagePublication',
  components: {
    AppDataTable,
    AppPagination,
  },
  setup() {
    const route = useRoute();

    // Reactive publication data for SEO
    const publicationForSeo = ref(null);

    // Breadcrumbs for structured data
    const seoBreadcrumbs = computed(() => [
      { name: 'Home', url: '/' },
      { name: 'Publications', url: '/publications' },
      {
        name: `PMID: ${route.params.publication_id || ''}`,
        url: `/publications/${route.params.publication_id || ''}`,
      },
    ]);

    // Apply SEO meta tags
    usePublicationSeo(publicationForSeo);
    usePublicationStructuredData(publicationForSeo);
    useBreadcrumbStructuredData(seoBreadcrumbs);

    // Expose setter for Options API
    const updateSeoPublication = (pub) => {
      publicationForSeo.value = pub;
    };

    return { updateSeoPublication };
  },
  data() {
    return {
      publicationId: null,
      publication: null,
      phenopackets: [],
      loading: false,
      phenopacketsLoading: false,
      error: null,
      activeTab: 'overview',

      // Pagination state
      pagination: {
        currentPage: 1,
        pageSize: 20,
        totalPages: 0,
        totalRecords: 0,
      },

      // Table configuration
      headers: [
        { title: 'Phenopacket ID', value: 'id', sortable: true, width: '200px' },
        { title: 'Subject ID', value: 'subject_id', sortable: true, width: '150px' },
        { title: 'Sex', value: 'subject_sex', sortable: true, width: '100px' },
        {
          title: 'Phenotypes',
          value: 'features_count',
          sortable: true,
          width: '100px',
          align: 'center',
        },
        {
          title: 'Variants',
          value: 'variants_count',
          sortable: true,
          width: '100px',
          align: 'center',
        },
      ],

      // Table options (for Vuetify data table)
      tableOptions: {
        page: 1,
        itemsPerPage: 20,
        sortBy: [{ key: 'id', order: 'asc' }],
      },
      itemsPerPageOptions: [10, 20, 50],
      loadingInitialized: false,
      previousSortBy: [{ key: 'id', order: 'asc' }],
    };
  },
  computed: {
    breadcrumbs() {
      return [
        { title: 'Home', to: '/', disabled: false },
        { title: 'Publications', to: '/publications', disabled: false },
        { title: `PMID: ${this.publicationId}`, disabled: true },
      ];
    },
  },
  mounted() {
    this.publicationId = this.$route.params.publication_id;
    this.fetchPublication();
  },
  methods: {
    async fetchPublication() {
      this.loading = true;
      this.error = null;

      window.logService.debug('Loading publication detail page', {
        publicationId: this.publicationId,
        route: this.$route.path,
      });

      try {
        // Fetch publication metadata from backend API
        const metadataResponse = await getPublicationMetadata(this.publicationId);
        this.publication = metadataResponse.data?.data || metadataResponse.data || {};

        window.logService.debug('Publication metadata received', {
          publicationId: this.publicationId,
          title: this.publication.title?.substring(0, 50),
        });

        // Fetch initial phenopackets
        await this.fetchPhenopackets();

        // Update SEO meta tags with publication data
        this.updateSeoPublication({
          ...this.publication,
          pmid: this.publicationId,
        });

        window.logService.info('Publication loaded successfully', {
          publicationId: this.publicationId,
          phenopacketCount: this.pagination.totalRecords,
        });
      } catch (error) {
        window.logService.error('Failed to fetch publication', {
          error: error.message,
          publicationId: this.publicationId,
          status: error.response?.status,
        });

        if (error.response?.status === 404) {
          this.error = `Publication 'PMID:${this.publicationId}' not found.`;
        } else {
          this.error = 'Failed to load publication. Please try again later.';
        }
      } finally {
        this.loading = false;
      }
    },

    async fetchPhenopackets() {
      this.phenopacketsLoading = true;

      try {
        const { sortBy } = this.tableOptions;

        // Map frontend column keys to backend sort field names
        const sortFieldMap = {
          id: 'id',
          subject_id: 'subject_id',
          subject_sex: 'subject_sex',
          features_count: 'id', // No direct mapping, sort by ID
          variants_count: 'id', // No direct mapping, sort by ID
        };

        const sortParam = buildSortParameter(sortBy, sortFieldMap) || 'id';

        const requestParams = {
          'page[number]': this.pagination.currentPage,
          'page[size]': this.pagination.pageSize,
          sort: sortParam,
        };

        const response = await getPhenopacketsByPublication(this.publicationId, requestParams);

        // Extract phenopacket objects from the wrapper
        const jsonApiData = response.data || {};
        const items = jsonApiData.data || [];
        const meta = jsonApiData.meta?.page || {};

        // The API returns {phenopacket_id, phenopacket} objects, extract the phenopacket
        this.phenopackets = items.map((item) => item.phenopacket || item);

        this.pagination.currentPage = meta.currentPage || this.pagination.currentPage;
        this.pagination.totalPages = meta.totalPages || 0;
        this.pagination.totalRecords = meta.totalRecords || items.length;

        window.logService.debug('Phenopackets fetched', {
          count: this.phenopackets.length,
          total: this.pagination.totalRecords,
          page: this.pagination.currentPage,
        });
      } catch (error) {
        window.logService.error('Failed to fetch phenopackets', {
          error: error.message,
          publicationId: this.publicationId,
        });
        this.phenopackets = [];
      } finally {
        this.phenopacketsLoading = false;
      }
    },

    onOptionsUpdate(newOptions) {
      // Preserve initial sort if Vuetify sends empty sortBy on first mount
      if (!this.loadingInitialized && (!newOptions.sortBy || newOptions.sortBy.length === 0)) {
        newOptions.sortBy = [{ key: 'id', order: 'asc' }];
        this.tableOptions.sortBy = [{ key: 'id', order: 'asc' }];
      }

      // Compare with previousSortBy since v-model updates this.tableOptions before handler
      const sortChanged = JSON.stringify(this.previousSortBy) !== JSON.stringify(newOptions.sortBy);

      // Store current sortBy for next comparison
      this.previousSortBy = newOptions.sortBy ? [...newOptions.sortBy] : [];
      this.tableOptions = { ...newOptions };

      if (!this.loadingInitialized) {
        this.loadingInitialized = true;
        // Initial fetch already done in mounted
      } else if (sortChanged) {
        this.resetPaginationAndFetch();
      }
    },

    customSort(items) {
      // Server-side sorting - return items as-is
      return items;
    },

    resetPaginationAndFetch() {
      this.pagination.currentPage = 1;
      this.pagination.totalPages = 0;
      this.fetchPhenopackets();
    },

    onPageSizeChange(newSize) {
      this.pagination.pageSize = newSize;
      this.resetPaginationAndFetch();
    },

    goToPage(page) {
      if (page < 1 || page > this.pagination.totalPages) return;
      this.pagination.currentPage = page;
      this.fetchPhenopackets();
    },

    handleRowClick(event, { item }) {
      if (item?.id) {
        this.$router.push(`/phenopackets/${item.id}`);
      }
    },

    // Formatting helpers
    formatAuthors(authors) {
      if (!authors) return '';
      if (typeof authors === 'string') return authors;
      if (Array.isArray(authors)) {
        const names = authors.map((a) => (typeof a === 'string' ? a : a.name)).filter(Boolean);
        if (names.length === 0) return '';
        if (names.length <= 3) return names.join(', ');
        return `${names[0]} et al.`;
      }
      return '';
    },

    truncateTitle(title, maxLength = 60) {
      if (!title) return 'Publication';
      if (title.length <= maxLength) return title;
      return title.substring(0, maxLength) + '...';
    },

    getSexColor(sex) {
      const colors = {
        MALE: 'blue-lighten-3',
        FEMALE: 'pink-lighten-3',
        OTHER_SEX: 'grey-lighten-2',
        UNKNOWN_SEX: 'grey-lighten-2',
      };
      return colors[sex] || 'grey-lighten-2';
    },

    getSexIcon(sex) {
      const icons = {
        MALE: 'mdi-gender-male',
        FEMALE: 'mdi-gender-female',
        OTHER_SEX: 'mdi-gender-non-binary',
        UNKNOWN_SEX: 'mdi-help-circle-outline',
      };
      return icons[sex] || 'mdi-help-circle-outline';
    },

    formatSex(sex) {
      const labels = {
        MALE: 'Male',
        FEMALE: 'Female',
        OTHER_SEX: 'Other',
        UNKNOWN_SEX: 'Unknown',
      };
      return labels[sex] || sex;
    },

    getVariantCount(item) {
      // Count variants from interpretations
      if (!item.interpretations) return 0;
      return item.interpretations.reduce((count, interp) => {
        const diagnosis = interp.diagnosis;
        if (diagnosis?.genomicInterpretations) {
          return count + diagnosis.genomicInterpretations.length;
        }
        return count;
      }, 0);
    },
  },
};
</script>

<style scoped>
.publication-container {
  min-height: 100vh;
}

.hero-section {
  background: linear-gradient(180deg, rgba(251, 140, 0, 0.05) 0%, transparent 100%);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

/* Clickable row styling for phenopacket navigation */
:deep(.clickable-row) {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

:deep(.clickable-row:hover) {
  background-color: rgba(var(--v-theme-primary), 0.08) !important;
}
</style>
