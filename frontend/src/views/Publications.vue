<!-- src/views/Publications.vue -->
<!--
  Publications Registry with server-side pagination following JSON:API v1.1 spec.

  Features:
  - Server-side pagination with page numbers (1, 2, 3... n)
  - Server-side sorting via JSON:API sort parameter
  - Client-side search filtering (dataset is small, ~50 publications)
  - Go to Last Page button
  - Consistent UI/UX with Variants and Phenopackets tables
-->
<template>
  <v-container fluid>
    <!-- Unified Table with Integrated Search Toolbar -->
    <AppDataTable
      v-model:options="options"
      :headers="headers"
      :items="publications"
      :loading="loading"
      :items-length="publications.length"
      :custom-sort="customSort"
      hide-default-footer
      title="Publications Registry"
      row-class="clickable-row"
      @update:options="onOptionsUpdate"
      @click:row="handleRowClick"
    >
      <!-- Integrated Search Toolbar -->
      <template #toolbar>
        <AppTableToolbar
          v-model:search-query="searchQuery"
          search-placeholder="Search PMID, DOI, title, or author..."
          :result-count="pagination.totalRecords"
          result-label="publications"
          :loading="loading"
          @search="onSearch"
          @clear-search="clearSearch"
        />
      </template>

      <!-- Pagination controls above table -->
      <template #top>
        <AppPagination
          :current-count="publications.length"
          :current-page="pagination.currentPage"
          :page-size="pagination.pageSize"
          :total-pages="pagination.totalPages"
          :total-records="pagination.totalRecords"
          :items-per-page-options="itemsPerPageOptions"
          @go-to-page="goToPage"
          @update:page-size="onPageSizeChange"
        />
      </template>

      <!-- Pagination controls below table -->
      <template #bottom>
        <AppPagination
          :current-count="publications.length"
          :current-page="pagination.currentPage"
          :page-size="pagination.pageSize"
          :total-pages="pagination.totalPages"
          :total-records="pagination.totalRecords"
          :items-per-page-options="itemsPerPageOptions"
          @go-to-page="goToPage"
          @update:page-size="onPageSizeChange"
        />
      </template>

      <!-- Render PMID as internal navigation chip (links to our detail page) -->
      <template #item.pmid="{ item }">
        <v-chip
          v-if="item.pmid"
          :to="`/publications/${extractPmidNumber(item.pmid)}`"
          color="orange-lighten-3"
          size="x-small"
          variant="flat"
        >
          <v-icon start size="x-small">mdi-book-open-variant</v-icon>
          {{ item.pmid }}
        </v-chip>
        <span v-else class="text-body-2 text-medium-emphasis">-</span>
      </template>

      <!-- External links column with PubMed and DOI icons -->
      <template #item.external_links="{ item }">
        <div class="d-flex align-center ga-1">
          <!-- PubMed external link -->
          <v-tooltip v-if="item.pmid" location="top" text="View on PubMed">
            <template #activator="{ props }">
              <v-btn
                v-bind="props"
                :href="`https://pubmed.ncbi.nlm.nih.gov/${extractPmidNumber(item.pmid)}`"
                target="_blank"
                icon
                size="x-small"
                variant="text"
                color="orange-darken-2"
              >
                <v-icon size="small">mdi-book-open-variant</v-icon>
              </v-btn>
            </template>
          </v-tooltip>
          <!-- DOI external link -->
          <v-tooltip v-if="item.doi" location="top" text="View DOI">
            <template #activator="{ props }">
              <v-btn
                v-bind="props"
                :href="`https://doi.org/${item.doi}`"
                target="_blank"
                icon
                size="x-small"
                variant="text"
                color="blue-darken-2"
              >
                <v-icon size="small">mdi-link-variant</v-icon>
              </v-btn>
            </template>
          </v-tooltip>
          <span v-if="!item.pmid && !item.doi" class="text-body-2 text-medium-emphasis">-</span>
        </div>
      </template>

      <!-- Render phenopacket count as clickable chip -->
      <template #item.phenopacket_count="{ item }">
        <v-chip
          color="green-lighten-3"
          size="x-small"
          variant="flat"
          :to="`/publications/${extractPmidNumber(item.pmid)}`"
          link
        >
          <v-icon start size="x-small">mdi-account-multiple</v-icon>
          {{ item.phenopacket_count }}
        </v-chip>
      </template>

      <!-- Format date -->
      <template #item.first_added="{ item }">
        <span class="text-body-2">{{ formatDate(item.first_added) }}</span>
      </template>

      <template #no-data>
        <v-alert type="info" variant="tonal" density="compact">
          No publications found. Publications are extracted from phenopacket metadata.
        </v-alert>
      </template>
    </AppDataTable>
  </v-container>
</template>

<script>
import { getPublications } from '@/api';
import { buildSortParameter } from '@/utils/pagination';
import AppDataTable from '@/components/common/AppDataTable.vue';
import AppTableToolbar from '@/components/common/AppTableToolbar.vue';
import AppPagination from '@/components/common/AppPagination.vue';

export default {
  name: 'Publications',
  components: {
    AppDataTable,
    AppTableToolbar,
    AppPagination,
  },
  data() {
    return {
      publications: [],
      searchQuery: '',
      loading: false,

      // Offset pagination state (JSON:API v1.1)
      pagination: {
        currentPage: 1,
        pageSize: 10,
        totalPages: 0,
        totalRecords: 0,
      },

      // Table configuration
      headers: [
        { title: 'PMID', value: 'pmid', sortable: true, width: '140px' },
        { title: 'Title', value: 'title', sortable: true, width: '300px' },
        { title: 'Authors', value: 'authors', sortable: true, width: '180px' },
        {
          title: 'Individuals',
          value: 'phenopacket_count',
          sortable: true,
          width: '100px',
          align: 'center',
        },
        { title: 'First Added', value: 'first_added', sortable: true, width: '120px' },
        {
          title: 'Links',
          value: 'external_links',
          sortable: false,
          width: '80px',
          align: 'center',
        },
      ],

      // Default sort configuration
      defaultSortBy: [{ key: 'phenopacket_count', order: 'desc' }],

      // Table options (for Vuetify data table)
      options: {
        page: 1,
        itemsPerPage: 10,
        sortBy: [{ key: 'phenopacket_count', order: 'desc' }],
      },
      itemsPerPageOptions: [10, 20, 50, 100],

      // Initialization flag
      loadingInitialized: false,

      // Track previous sortBy for change detection (v-model updates this.options before handler)
      previousSortBy: [{ key: 'phenopacket_count', order: 'desc' }],
    };
  },
  methods: {
    /**
     * Fetch publications from the server with JSON:API offset pagination.
     */
    async fetchPublications() {
      this.loading = true;
      window.logService.debug('Fetching publications', {
        page: this.pagination.currentPage,
        sortBy: this.options.sortBy,
        search: this.searchQuery,
      });

      try {
        const { sortBy } = this.options;

        // Map frontend column keys to backend sort field names
        const sortFieldMap = {
          pmid: 'pmid',
          title: 'title',
          authors: 'authors',
          phenopacket_count: 'phenopacket_count',
          first_added: 'first_added',
        };

        const sortParam = buildSortParameter(sortBy, sortFieldMap) || '-phenopacket_count';

        // Build request params for offset pagination
        const requestParams = {
          'page[number]': this.pagination.currentPage,
          'page[size]': this.pagination.pageSize,
          sort: sortParam,
        };

        // Add search query if present
        if (this.searchQuery?.trim()) {
          requestParams.q = this.searchQuery.trim();
        }

        const response = await getPublications(requestParams);

        // Extract JSON:API response data
        const jsonApiData = response.data || {};
        const publicationItems = jsonApiData.data || [];
        const meta = jsonApiData.meta?.page || {};

        this.publications = publicationItems;
        this.pagination.currentPage = meta.currentPage || this.pagination.currentPage;
        this.pagination.totalPages = meta.totalPages || 0;
        this.pagination.totalRecords = meta.totalRecords || 0;

        window.logService.info('Publications fetched', {
          count: publicationItems.length,
          total: meta.totalRecords,
          page: this.pagination.currentPage,
        });
      } catch (error) {
        window.logService.error('Failed to fetch publications', {
          error: error.message,
          status: error.response?.status,
        });
        this.publications = [];
      } finally {
        this.loading = false;
      }
    },

    resetPaginationAndFetch() {
      this.pagination.currentPage = 1;
      this.pagination.totalPages = 0;
      this.pagination.totalRecords = 0;
      this.fetchPublications();
    },

    // Event handlers
    onOptionsUpdate(newOptions) {
      // Preserve initial sort if Vuetify sends empty sortBy on first mount
      if (!this.loadingInitialized && (!newOptions.sortBy || newOptions.sortBy.length === 0)) {
        newOptions.sortBy = [...this.defaultSortBy];
        this.options.sortBy = [...this.defaultSortBy];
      }

      // Compare with previousSortBy since v-model updates this.options before handler
      const sortChanged = JSON.stringify(this.previousSortBy) !== JSON.stringify(newOptions.sortBy);

      // Store current sortBy for next comparison
      this.previousSortBy = newOptions.sortBy ? [...newOptions.sortBy] : [];
      this.options = { ...newOptions };

      if (!this.loadingInitialized) {
        this.loadingInitialized = true;
        this.fetchPublications();
      } else if (sortChanged) {
        this.resetPaginationAndFetch();
      }
    },

    customSort(items) {
      // Server-side sorting - return items as-is
      return items;
    },

    onSearch() {
      this.resetPaginationAndFetch();
    },

    clearSearch() {
      this.searchQuery = '';
      this.resetPaginationAndFetch();
    },

    onPageSizeChange(newSize) {
      this.pagination.pageSize = newSize;
      this.resetPaginationAndFetch();
    },

    goToPage(page) {
      if (page < 1 || page > this.pagination.totalPages) return;
      this.pagination.currentPage = page;
      this.fetchPublications();
    },

    formatDate(dateString) {
      if (!dateString) return '-';
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    },

    /**
     * Extract numeric PMID from format "PMID:12345678".
     * Handles both "PMID:12345678" and plain "12345678" formats.
     */
    extractPmidNumber(pmid) {
      if (!pmid) return '';
      return String(pmid).replace('PMID:', '');
    },

    /**
     * Handle row click to navigate to publication detail page.
     * Uses extractPmidNumber to handle PMID format consistently.
     */
    handleRowClick(event, { item }) {
      if (item?.pmid) {
        this.$router.push(`/publications/${this.extractPmidNumber(item.pmid)}`);
      }
    },
  },
};
</script>

<style scoped>
/* Clickable row styling for publication navigation */
:deep(.clickable-row) {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

:deep(.clickable-row:hover) {
  background-color: rgba(var(--v-theme-primary), 0.08) !important;
}
</style>
