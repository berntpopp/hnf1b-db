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
      <template #header.variant_type="{ column, toggleSort }">
        <div class="d-flex align-center justify-space-between header-wrapper">
          <div class="d-flex align-center flex-grow-1 sortable-header" @click="toggleSort(column)">
            <span class="header-title">{{ column.title }}</span>
          </div>
          <v-menu :close-on-content-click="false" location="bottom">
            <template #activator="{ props }">
              <v-btn
                icon
                size="x-small"
                variant="text"
                v-bind="props"
                :color="filterValues.type ? 'primary' : 'default'"
              >
                <v-icon size="small">
                  {{ filterValues.type ? 'mdi-filter' : 'mdi-filter-outline' }}
                </v-icon>
              </v-btn>
            </template>
            <v-card min-width="200" max-width="280">
              <v-card-title class="text-subtitle-2 py-2 d-flex align-center">
                <v-icon size="small" class="mr-2">mdi-dna</v-icon>
                Filter: Type
              </v-card-title>
              <v-divider />
              <v-card-text class="pa-3">
                <v-select
                  v-model="filterValues.type"
                  :items="variantTypes"
                  label="Select type"
                  density="compact"
                  variant="outlined"
                  clearable
                  hide-details
                />
              </v-card-text>
              <v-divider />
              <v-card-actions class="pa-2">
                <v-spacer />
                <v-btn size="small" variant="text" @click="clearFilter('type')">Clear</v-btn>
              </v-card-actions>
            </v-card>
          </v-menu>
        </div>
      </template>

      <!-- Column Header: Classification with filter menu -->
      <template #header.classificationVerdict="{ column, getSortIcon, toggleSort, isSorted }">
        <div class="d-flex align-center justify-space-between header-wrapper">
          <div class="d-flex align-center flex-grow-1 sortable-header" @click="toggleSort(column)">
            <span class="header-title">{{ column.title }}</span>
            <v-icon v-if="isSorted(column)" size="small" class="ml-1">
              {{ getSortIcon(column) }}
            </v-icon>
          </div>
          <v-menu :close-on-content-click="false" location="bottom">
            <template #activator="{ props }">
              <v-btn
                icon
                size="x-small"
                variant="text"
                v-bind="props"
                :color="filterValues.classification ? 'primary' : 'default'"
              >
                <v-icon size="small">
                  {{ filterValues.classification ? 'mdi-filter' : 'mdi-filter-outline' }}
                </v-icon>
              </v-btn>
            </template>
            <v-card min-width="220" max-width="300">
              <v-card-title class="text-subtitle-2 py-2 d-flex align-center">
                <v-icon size="small" class="mr-2">mdi-alert-circle</v-icon>
                Filter: Classification
              </v-card-title>
              <v-divider />
              <v-card-text class="pa-3">
                <v-select
                  v-model="filterValues.classification"
                  :items="classifications"
                  label="Select classification"
                  density="compact"
                  variant="outlined"
                  clearable
                  hide-details
                />
              </v-card-text>
              <v-divider />
              <v-card-actions class="pa-2">
                <v-spacer />
                <v-btn size="small" variant="text" @click="clearFilter('classification')">
                  Clear
                </v-btn>
              </v-card-actions>
            </v-card>
          </v-menu>
        </div>
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
        <v-tooltip v-if="item.hg38 && item.hg38.length > 30" location="top">
          <template #activator="{ props }">
            <span
              v-bind="props"
              class="text-truncate d-inline-block text-body-2"
              style="max-width: 200px; cursor: help"
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
import { buildSortParameter } from '@/utils/pagination';
import AppDataTable from '@/components/common/AppDataTable.vue';
import AppTableToolbar from '@/components/common/AppTableToolbar.vue';
import AppPagination from '@/components/common/AppPagination.vue';

export default {
  name: 'Variants',
  components: {
    AppDataTable,
    AppTableToolbar,
    AppPagination,
  },
  data() {
    return {
      // Search and filter state
      searchQuery: '',
      filterValues: {
        type: null,
        classification: null,
      },

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
    hasActiveFilters() {
      return !!(this.searchQuery || this.filterValues.type || this.filterValues.classification);
    },

    activeFilterCount() {
      let count = 0;
      if (this.searchQuery) count++;
      if (this.filterValues.type) count++;
      if (this.filterValues.classification) count++;
      return count;
    },
  },
  watch: {
    filterValues: {
      handler() {
        if (this.loadingInitialized) {
          this.resetPaginationAndFetch();
        }
      },
      deep: true,
    },
  },
  methods: {
    async fetchVariants() {
      this.loading = true;
      window.logService.debug('Fetching variants', {
        page: this.pagination.currentPage,
        sortBy: this.options.sortBy,
        filters: { searchQuery: this.searchQuery, ...this.filterValues },
      });

      try {
        const { sortBy } = this.options;

        // Map frontend column keys to backend sort field names
        const sortFieldMap = {
          simple_id: 'simple_id',
          transcript: 'transcript',
          protein: 'protein',
          variant_type: 'variant_type',
          hg38: 'hg38',
          classificationVerdict: 'classificationVerdict',
          individualCount: 'individualCount',
        };

        const sortParam = buildSortParameter(sortBy, sortFieldMap);

        const requestParams = {
          page: this.pagination.currentPage,
          pageSize: this.pagination.pageSize,
          ...(sortParam && { sort: sortParam }),
          ...(this.searchQuery && { query: this.searchQuery }),
          ...(this.filterValues.type && { variant_type: this.filterValues.type }),
          ...(this.filterValues.classification && {
            classification: this.filterValues.classification,
          }),
        };

        const response = await getVariants(requestParams);

        this.variants = response.data;
        this.pagination.currentPage = response.meta.currentPage;
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

    resetPaginationAndFetch() {
      this.pagination.currentPage = 1;
      this.pagination.totalPages = 0;
      this.pagination.totalRecords = 0;
      this.fetchVariants();
    },

    // Event handlers
    onSearch() {
      this.resetPaginationAndFetch();
    },

    onClearSearch() {
      this.searchQuery = '';
      this.resetPaginationAndFetch();
    },

    onPageSizeChange(newSize) {
      this.pagination.pageSize = newSize;
      this.resetPaginationAndFetch();
    },

    clearFilter(key) {
      this.filterValues[key] = null;
    },

    clearAllFilters() {
      this.searchQuery = '';
      this.filterValues = { type: null, classification: null };
      this.resetPaginationAndFetch();
    },

    // Utility functions
    getVariantType,
    extractCNotation,
    extractPNotation,
    getPathogenicityColor,
    getVariantTypeColor,

    onOptionsUpdate(newOptions) {
      // Preserve initial sort if Vuetify sends empty sortBy on first mount
      // Note: v-model:options overwrites this.options BEFORE this handler runs,
      // so we use the separate defaultSortBy constant
      if (!this.loadingInitialized && (!newOptions.sortBy || newOptions.sortBy.length === 0)) {
        newOptions.sortBy = [...this.defaultSortBy];
        // Also restore options.sortBy so Vuetify shows the sort indicator
        this.options.sortBy = [...this.defaultSortBy];
      }

      // Compare with previousSortBy since v-model updates this.options before handler
      const sortChanged = JSON.stringify(this.previousSortBy) !== JSON.stringify(newOptions.sortBy);

      // Store current sortBy for next comparison
      this.previousSortBy = newOptions.sortBy ? [...newOptions.sortBy] : [];
      this.options = { ...newOptions };

      if (!this.loadingInitialized) {
        this.loadingInitialized = true;
        this.fetchVariants();
      } else if (sortChanged) {
        this.resetPaginationAndFetch();
      }
    },

    customSort(items) {
      return items;
    },

    goToPage(page) {
      if (page < 1 || page > this.pagination.totalPages) return;
      this.pagination.currentPage = page;
      this.fetchVariants();
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

/* Header wrapper for filter buttons */
.header-wrapper {
  width: 100%;
  gap: 4px;
}

.sortable-header {
  cursor: pointer;
  user-select: none;
  transition: opacity 0.2s;
  min-width: 0;
}

.sortable-header:hover {
  opacity: 0.7;
}

.header-title {
  font-weight: 600;
  font-size: 0.75rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: #37474f;
}
</style>
