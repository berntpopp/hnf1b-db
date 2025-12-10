<!-- src/views/Variants.vue -->
<template>
  <v-container fluid>
    <!-- Unified Table with Column-Based Filtering -->
    <AppDataTable
      v-model:options="options"
      :headers="headers"
      :items="variants"
      :loading="loading"
      :items-length="variants.length"
      :custom-sort="customSort"
      hide-default-footer
      title="Variants Registry"
      @update:options="onOptionsUpdate"
      @click:row="handleRowClick"
    >
      <!-- Simplified Search Toolbar -->
      <template #toolbar>
        <AppTableToolbar
          v-model:search-query="searchQuery"
          search-placeholder="Search HGVS, gene symbol, or variant ID..."
          :result-count="pagination.totalRecords"
          result-label="variants"
          :loading="loading"
          @search="onSearch"
          @clear-search="onClearSearch"
        >
          <template #actions>
            <!-- Clear filters button -->
            <v-btn
              v-if="hasActiveFilters"
              variant="text"
              size="small"
              color="warning"
              @click="clearAllFilters"
            >
              <v-icon start size="small">mdi-filter-off</v-icon>
              Clear Filters ({{ activeFilterCount }})
            </v-btn>
          </template>
        </AppTableToolbar>
      </template>

      <!-- Pagination controls above table -->
      <template #top>
        <AppPagination
          :current-count="variants.length"
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
          :current-count="variants.length"
          :current-page="pagination.currentPage"
          :page-size="pagination.pageSize"
          :total-pages="pagination.totalPages"
          :total-records="pagination.totalRecords"
          :items-per-page-options="itemsPerPageOptions"
          @go-to-page="goToPage"
          @update:page-size="onPageSizeChange"
        />
      </template>

      <!-- Column Header: Type with filter menu -->
      <template #header.variant_type="{ column, getSortIcon, toggleSort, isSorted }">
        <ColumnHeaderFilter
          v-model="typeFilter"
          :title="column.title"
          :options="variantTypes"
          select-label="Select type"
          filter-icon="mdi-dna"
          :sort-icon="isSorted(column) ? getSortIcon(column) : null"
          @sort="toggleSort(column)"
          @clear="clearFilter('type')"
        />
      </template>

      <!-- Column Header: Classification with filter menu -->
      <template #header.classificationVerdict="{ column, getSortIcon, toggleSort, isSorted }">
        <ColumnHeaderFilter
          v-model="classificationFilter"
          :title="column.title"
          :options="classifications"
          select-label="Select classification"
          filter-icon="mdi-alert-circle"
          :sort-icon="isSorted(column) ? getSortIcon(column) : null"
          @sort="toggleSort(column)"
          @clear="clearFilter('classification')"
        />
      </template>

      <!-- Render simple_id as a clickable chip -->
      <template #item.simple_id="{ item }">
        <v-chip color="pink-lighten-3" size="x-small" variant="flat">
          {{ item.simple_id }}
          <v-icon end size="x-small">mdi-dna</v-icon>
        </v-chip>
      </template>

      <!-- Render transcript with only c. notation -->
      <template #item.transcript="{ item }">
        <span class="text-body-2">{{ extractCNotation(item.transcript) }}</span>
      </template>

      <!-- Render protein with only p. notation -->
      <template #item.protein="{ item }">
        <span class="text-body-2">{{ extractPNotation(item.protein) }}</span>
      </template>

      <!-- Render variant type with color coding -->
      <template #item.variant_type="{ item }">
        <v-chip :color="getVariantTypeColor(getVariantType(item))" size="x-small" variant="flat">
          {{ getVariantType(item) }}
        </v-chip>
      </template>

      <!-- Render HG38 with truncation for long values -->
      <template #item.hg38="{ item }">
        <v-tooltip
          v-if="item.hg38 && item.hg38.length > 30"
          location="top"
          :aria-label="`Full HG38 coordinate: ${item.hg38}`"
        >
          <template #activator="{ props }">
            <span
              v-bind="props"
              class="text-truncate d-inline-block text-body-2"
              style="max-width: 200px; cursor: help"
              role="button"
              tabindex="0"
              :aria-label="`HG38 coordinate: ${item.hg38}`"
            >
              {{ item.hg38 }}
            </span>
          </template>
          <span style="word-break: break-all; max-width: 400px; display: block">{{
            item.hg38
          }}</span>
        </v-tooltip>
        <span v-else class="text-body-2">{{ item.hg38 || '-' }}</span>
      </template>

      <!-- Render classification with color coding -->
      <template #item.classificationVerdict="{ item }">
        <v-chip
          v-if="item.classificationVerdict"
          :color="getPathogenicityColor(item.classificationVerdict)"
          size="x-small"
          variant="flat"
        >
          {{ item.classificationVerdict }}
        </v-chip>
        <span v-else class="text-body-2 text-medium-emphasis">-</span>
      </template>

      <!-- Render individual count as a badge -->
      <template #item.individualCount="{ item }">
        <v-chip color="light-green-lighten-3" size="x-small" variant="flat">
          {{ item.individualCount || 0 }}
        </v-chip>
      </template>

      <template #no-data>
        <v-empty-state
          v-if="hasActiveFilters"
          icon="mdi-filter-off"
          title="No variants found"
          text="Try adjusting your search or filters."
        >
          <template #actions>
            <v-btn color="primary" size="small" @click="clearAllFilters">Clear Filters</v-btn>
          </template>
        </v-empty-state>
        <span v-else class="text-body-2 text-medium-emphasis">No variants found.</span>
      </template>
    </AppDataTable>
  </v-container>
</template>

<script>
import { getVariants } from '@/api';
import { extractCNotation, extractPNotation } from '@/utils/hgvs';
import { getPathogenicityColor, getVariantTypeColor } from '@/utils/colors';
import { getVariantType } from '@/utils/variants';
import { useTableUrlState } from '@/composables/useTableUrlState';
import AppDataTable from '@/components/common/AppDataTable.vue';
import AppTableToolbar from '@/components/common/AppTableToolbar.vue';
import AppPagination from '@/components/common/AppPagination.vue';
import ColumnHeaderFilter from '@/components/common/ColumnHeaderFilter.vue';

export default {
  name: 'Variants',
  components: {
    AppDataTable,
    AppTableToolbar,
    AppPagination,
    ColumnHeaderFilter,
  },
  setup() {
    // URL state synchronization for shareable/bookmarkable URLs
    // Return entire urlState to preserve ref reactivity in Options API
    const urlState = useTableUrlState({
      defaultPageSize: 10,
      defaultSort: '-simple_id',
      filters: { type: null, classification: null },
    });

    return { urlState };
  },
  data() {
    return {
      // Table data
      variants: [],
      loading: false,

      // Offset pagination state
      pagination: {
        currentPage: 1,
        pageSize: 10,
        totalPages: 0,
        totalRecords: 0,
      },

      // Initialization flag
      loadingInitialized: false,

      // Track previous sortBy for change detection (v-model updates this.options before handler)
      previousSortBy: [{ key: 'simple_id', order: 'desc' }],

      // Filter options
      variantTypes: ['SNV', 'CNV', 'deletion', 'duplication', 'insertion', 'indel'],
      classifications: [
        'PATHOGENIC',
        'LIKELY_PATHOGENIC',
        'UNCERTAIN_SIGNIFICANCE',
        'LIKELY_BENIGN',
        'BENIGN',
      ],

      // Table configuration
      // All sortable columns are server-side sorted via JSON:API sort parameter
      headers: [
        { title: 'Variant ID', value: 'simple_id', sortable: true, width: '100px' },
        { title: 'Transcript (c.)', value: 'transcript', sortable: true, width: '160px' },
        { title: 'Protein (p.)', value: 'protein', sortable: true, width: '140px' },
        { title: 'Type', value: 'variant_type', sortable: true, width: '100px' },
        { title: 'HG38', value: 'hg38', sortable: true, width: '200px' },
        { title: 'Classification', value: 'classificationVerdict', sortable: true, width: '140px' },
        {
          title: 'Individuals',
          value: 'individualCount',
          sortable: true,
          width: '90px',
          align: 'center',
        },
      ],

      // Default sort configuration (preserved separately from v-model binding)
      // Vuetify's v-model:options overwrites sortBy on mount, so we keep a copy
      defaultSortBy: [{ key: 'simple_id', order: 'desc' }],

      // Table options (for Vuetify data table)
      options: {
        page: 1,
        itemsPerPage: 10,
        sortBy: [{ key: 'simple_id', order: 'desc' }],
      },
      itemsPerPageOptions: [10, 20, 50, 100],
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
    // Direct computed for type filter - v-model compatible
    typeFilter: {
      get() {
        return this.urlState?.filters?.type?.value ?? null;
      },
      set(value) {
        if (this.urlState?.filters?.type) {
          this.urlState.filters.type.value = value;
        }
      },
    },
    // Direct computed for classification filter - v-model compatible
    classificationFilter: {
      get() {
        return this.urlState?.filters?.classification?.value ?? null;
      },
      set(value) {
        if (this.urlState?.filters?.classification) {
          this.urlState.filters.classification.value = value;
        }
      },
    },
    // Keep filterValues for compatibility (read-only)
    filterValues() {
      return {
        type: this.urlState?.filters?.type?.value ?? null,
        classification: this.urlState?.filters?.classification?.value ?? null,
      };
    },
    hasActiveFilters() {
      return (this.urlState?.activeFilterCount?.value ?? 0) > 0;
    },
    activeFilterCount() {
      return this.urlState?.activeFilterCount?.value ?? 0;
    },
  },
  watch: {
    // Watch URL filter changes
    'urlState.filters.type.value': {
      handler() {
        if (this.loadingInitialized) {
          this.urlState.resetPage();
          this.fetchVariants();
        }
      },
    },
    'urlState.filters.classification.value': {
      handler() {
        if (this.loadingInitialized) {
          this.urlState.resetPage();
          this.fetchVariants();
        }
      },
    },
    // Watch URL search changes
    'urlState.search.value': {
      handler() {
        if (this.loadingInitialized) {
          this.urlState.resetPage();
          this.fetchVariants();
        }
      },
    },
    // Watch URL page changes
    'urlState.page.value': {
      handler(newPage) {
        if (this.loadingInitialized && newPage !== this.pagination.currentPage) {
          this.pagination.currentPage = newPage;
          this.fetchVariants();
        }
      },
    },
    // Watch URL pageSize changes
    'urlState.pageSize.value': {
      handler(newPageSize) {
        if (this.loadingInitialized && newPageSize !== this.pagination.pageSize) {
          this.pagination.pageSize = newPageSize;
          this.urlState.resetPage();
          this.fetchVariants();
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
          this.fetchVariants();
        }
      },
    },
  },
  methods: {
    async fetchVariants() {
      this.loading = true;

      // Read state from URL state refs
      const currentPage = this.urlState?.page?.value ?? 1;
      const pageSize = this.urlState?.pageSize?.value ?? 10;
      const sortValue = this.urlState?.sort?.value ?? '-simple_id';
      const searchValue = this.urlState?.search?.value ?? '';
      const typeFilter = this.urlState?.filters?.type?.value ?? null;
      const classificationFilter = this.urlState?.filters?.classification?.value ?? null;

      window.logService.debug('Fetching variants', {
        page: currentPage,
        pageSize,
        sort: sortValue,
        filters: { search: searchValue, type: typeFilter, classification: classificationFilter },
      });

      try {
        const requestParams = {
          page: currentPage,
          pageSize: pageSize,
          ...(sortValue && { sort: sortValue }),
          ...(searchValue && { query: searchValue }),
          ...(typeFilter && { variant_type: typeFilter }),
          ...(classificationFilter && { classification: classificationFilter }),
        };

        const response = await getVariants(requestParams);

        this.variants = response.data;
        this.pagination.currentPage = response.meta.currentPage;
        this.pagination.pageSize = pageSize;
        this.pagination.totalPages = response.meta.totalPages;
        this.pagination.totalRecords = response.meta.totalRecords;

        window.logService.info('Variants fetched', { count: response.data?.length });
      } catch (error) {
        window.logService.error('Failed to fetch variants', { error: error.message });
        this.variants = [];
      } finally {
        this.loading = false;
      }
    },

    // URL state helper: Parse sort string to Vuetify sortBy format
    parseSortToVuetify(sortString) {
      if (!sortString) return [{ key: 'simple_id', order: 'desc' }];
      const descending = sortString.startsWith('-');
      const field = descending ? sortString.slice(1) : sortString;
      return [{ key: field, order: descending ? 'desc' : 'asc' }];
    },

    // URL state helper: Convert Vuetify sortBy to sort string
    vuetifyToSortString(sortBy) {
      if (!sortBy || sortBy.length === 0) return '-simple_id';
      const { key, order } = sortBy[0];
      return order === 'desc' ? `-${key}` : key;
    },

    // Event handlers
    onSearch() {
      // Search is already bound to urlState.search via computed setter
      // Just need to reset page when searching
      this.urlState.resetPage();
    },

    onClearSearch() {
      this.searchQuery = '';
      this.urlState.resetPage();
    },

    onPageSizeChange(newSize) {
      if (this.urlState?.pageSize) {
        this.urlState.pageSize.value = newSize;
      }
      this.urlState.resetPage();
    },

    clearFilter(key) {
      if (this.urlState?.filters?.[key]) {
        this.urlState.filters[key].value = null;
      }
      this.urlState.resetPage();
    },

    clearAllFilters() {
      this.urlState.clearAllFilters();
    },

    // Utility functions
    getVariantType,
    extractCNotation,
    extractPNotation,
    getPathogenicityColor,
    getVariantTypeColor,

    onOptionsUpdate(newOptions) {
      // Preserve initial sort if Vuetify sends empty sortBy on first mount
      if (!this.loadingInitialized && (!newOptions.sortBy || newOptions.sortBy.length === 0)) {
        // Get sort from URL or use default
        const urlSortValue = this.urlState?.sort?.value ?? '-simple_id';
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
        this.fetchVariants();
      } else if (sortChanged) {
        // User changed sort via table header click - sync to URL
        const newSortString = this.vuetifyToSortString(newOptions.sortBy);
        if (this.urlState?.sort) {
          this.urlState.sort.value = newSortString;
        }
        this.urlState.resetPage();
        this.fetchVariants();
      }
    },

    customSort(items) {
      // Server-side sorting, just return items as-is
      return items;
    },

    goToPage(page) {
      if (page < 1 || page > this.pagination.totalPages) return;
      // Update URL state, which triggers watch and fetch
      if (this.urlState?.page) {
        this.urlState.page.value = page;
      }
    },

    handleRowClick(event, row) {
      if (row.item?.variant_id) {
        window.logService.info('Navigating to variant', { variantId: row.item.variant_id });
        // URL-encode variant_id to handle special characters like colons
        this.$router.push(`/variants/${encodeURIComponent(row.item.variant_id)}`);
      }
    },
  },
};
</script>

<style scoped>
:deep(tbody tr) {
  cursor: pointer;
}
</style>
