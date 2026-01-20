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
  <PageHeader
    title="Publications"
    subtitle="Scientific literature on HNF1B variants and phenotypes"
    icon="mdi-file-document-multiple"
    icon-color="cyan-darken-1"
  />
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
      row-class="clickable-row"
      @update:options="onOptionsUpdate"
      @click:row="handleRowClick"
    >
      <!-- Integrated Search Toolbar -->
      <template #toolbar>
        <DataTableToolbar
          v-model:search-query="searchQuery"
          search-placeholder="Search PMID, DOI, title, or author..."
          :result-count="pagination.totalRecords"
          result-label="publications"
          :loading="loading"
          :active-filters="computedActiveFilters"
          @search="onSearch"
          @clear-search="clearSearch"
          @remove-filter="removeFilter"
          @clear-all-filters="clearAllFilters"
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
          <v-tooltip
            v-if="item.pmid"
            location="top"
            text="View on PubMed"
            aria-label="View on PubMed"
          >
            <template #activator="{ props }">
              <v-btn
                v-bind="props"
                :href="`https://pubmed.ncbi.nlm.nih.gov/${extractPmidNumber(item.pmid)}`"
                target="_blank"
                icon
                size="x-small"
                variant="text"
                color="orange-darken-2"
                aria-label="View on PubMed"
              >
                <v-icon size="small">mdi-book-open-variant</v-icon>
              </v-btn>
            </template>
          </v-tooltip>
          <!-- DOI external link -->
          <v-tooltip v-if="item.doi" location="top" text="View DOI" aria-label="View DOI">
            <template #activator="{ props }">
              <v-btn
                v-bind="props"
                :href="`https://doi.org/${item.doi}`"
                target="_blank"
                icon
                size="x-small"
                variant="text"
                color="blue-darken-2"
                aria-label="View DOI"
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
import { useTableUrlState } from '@/composables/useTableUrlState';
import AppDataTable from '@/components/common/AppDataTable.vue';
import AppPagination from '@/components/common/AppPagination.vue';
import PageHeader from '@/components/common/PageHeader.vue';
import DataTableToolbar from '@/components/common/DataTableToolbar.vue';

export default {
  name: 'Publications',
  components: {
    AppDataTable,
    AppPagination,
    PageHeader,
    DataTableToolbar,
  },
  setup() {
    // URL state synchronization for shareable/bookmarkable URLs
    // Return entire urlState to preserve ref reactivity in Options API
    const urlState = useTableUrlState({
      defaultPageSize: 10,
      defaultSort: '-phenopacket_count',
      filters: {}, // No column filters for publications
    });

    return { urlState };
  },
  data() {
    return {
      publications: [],
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
        { title: 'Authors', value: 'authors', sortable: false, width: '180px' },
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
  computed: {
    // Bridge URL state to component for v-model bindings
    searchQuery: {
      get() {
        return this.urlState?.search?.value ?? '';
      },
      set(value) {
        if (this.urlState?.search) {
          this.urlState.search.value = value;
        }
      },
    },
    /**
     * Computed active filters for DataTableToolbar chip display.
     * Publications has no column filters, returns empty array.
     */
    computedActiveFilters() {
      // Publications doesn't have column filters (only search)
      return [];
    },
  },
  watch: {
    // Watch URL search changes
    'urlState.search.value': {
      handler() {
        if (this.loadingInitialized) {
          this.urlState.resetPage();
          this.fetchPublications();
        }
      },
    },
    // Watch URL page changes
    'urlState.page.value': {
      handler(newPage) {
        if (this.loadingInitialized && newPage !== this.pagination.currentPage) {
          this.pagination.currentPage = newPage;
          this.fetchPublications();
        }
      },
    },
    // Watch URL pageSize changes
    'urlState.pageSize.value': {
      handler(newPageSize) {
        if (this.loadingInitialized && newPageSize !== this.pagination.pageSize) {
          this.pagination.pageSize = newPageSize;
          this.urlState.resetPage();
          this.fetchPublications();
        }
      },
    },
    // Watch URL sort changes
    'urlState.sort.value': {
      handler(newSort) {
        if (this.loadingInitialized) {
          // Update Vuetify options from URL sort
          this.options.sortBy = this.parseSortToVuetify(newSort);
          this.urlState.resetPage();
          this.fetchPublications();
        }
      },
    },
  },
  methods: {
    /**
     * Fetch publications from the server with JSON:API offset pagination.
     */
    async fetchPublications() {
      this.loading = true;

      // Read state from URL state refs
      const currentPage = this.urlState?.page?.value ?? 1;
      const pageSize = this.urlState?.pageSize?.value ?? 10;
      const sortValue = this.urlState?.sort?.value ?? '-phenopacket_count';
      const searchValue = this.urlState?.search?.value ?? '';

      window.logService.debug('Fetching publications', {
        page: currentPage,
        pageSize,
        sort: sortValue,
        search: searchValue,
      });

      try {
        // Build request params for offset pagination
        const requestParams = {
          'page[number]': currentPage,
          'page[size]': pageSize,
          sort: sortValue,
        };

        // Add search query if present
        if (searchValue?.trim()) {
          requestParams.q = searchValue.trim();
        }

        const response = await getPublications(requestParams);

        // Extract JSON:API response data
        const jsonApiData = response.data || {};
        const publicationItems = jsonApiData.data || [];
        const meta = jsonApiData.meta?.page || {};

        this.publications = publicationItems;
        this.pagination.currentPage = meta.currentPage || currentPage;
        this.pagination.pageSize = pageSize;
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

    // URL state helper: Parse sort string to Vuetify sortBy format
    parseSortToVuetify(sortString) {
      if (!sortString) return [{ key: 'phenopacket_count', order: 'desc' }];
      const descending = sortString.startsWith('-');
      const field = descending ? sortString.slice(1) : sortString;
      return [{ key: field, order: descending ? 'desc' : 'asc' }];
    },

    // URL state helper: Convert Vuetify sortBy to sort string
    vuetifyToSortString(sortBy) {
      if (!sortBy || sortBy.length === 0) return '-phenopacket_count';
      const { key, order } = sortBy[0];
      return order === 'desc' ? `-${key}` : key;
    },

    // Event handlers
    onOptionsUpdate(newOptions) {
      // Preserve initial sort if Vuetify sends empty sortBy on first mount
      if (!this.loadingInitialized && (!newOptions.sortBy || newOptions.sortBy.length === 0)) {
        // Get sort from URL or use default
        const urlSortValue = this.urlState?.sort?.value ?? '-phenopacket_count';
        newOptions.sortBy = this.parseSortToVuetify(urlSortValue);
        this.options.sortBy = [...newOptions.sortBy];
      }

      // Compare with previousSortBy to detect user-initiated sort changes
      const sortChanged = JSON.stringify(this.previousSortBy) !== JSON.stringify(newOptions.sortBy);

      // Store current sortBy for next comparison
      this.previousSortBy = newOptions.sortBy ? [...newOptions.sortBy] : [];
      this.options = { ...newOptions };

      if (!this.loadingInitialized) {
        // Initial load: sync pagination from URL state
        this.pagination.currentPage = this.urlState?.page?.value ?? 1;
        this.pagination.pageSize = this.urlState?.pageSize?.value ?? 10;
        this.loadingInitialized = true;
        this.fetchPublications();
      } else if (sortChanged) {
        // User changed sort via table header click - sync to URL
        const newSortString = this.vuetifyToSortString(newOptions.sortBy);
        if (this.urlState?.sort) {
          this.urlState.sort.value = newSortString;
        }
        this.urlState.resetPage();
        this.fetchPublications();
      }
    },

    customSort(items) {
      // Server-side sorting - return items as-is
      return items;
    },

    onSearch() {
      // Search is already bound to urlSearch via computed setter
      this.urlState.resetPage();
    },

    clearSearch() {
      this.searchQuery = '';
      this.urlState.resetPage();
    },

    /**
     * Remove a specific filter by key (used by DataTableToolbar chip close).
     * Publications has no column filters, so this is a no-op.
     */
    removeFilter() {
      // No column filters for publications, no-op
    },

    /**
     * Clear all filters (used by DataTableToolbar clear all button).
     * Publications only has search, so just clear search.
     */
    clearAllFilters() {
      this.clearSearch();
    },

    onPageSizeChange(newSize) {
      if (this.urlState?.pageSize) {
        this.urlState.pageSize.value = newSize;
      }
      this.urlState.resetPage();
    },

    goToPage(page) {
      if (page < 1 || page > this.pagination.totalPages) return;
      // Update URL state, which triggers watch and fetch
      if (this.urlState?.page) {
        this.urlState.page.value = page;
      }
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
