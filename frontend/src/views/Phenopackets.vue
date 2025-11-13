<!-- src/views/Phenopackets.vue -->
<template>
  <v-container>
    <v-data-table-server
      v-model:options="options"
      :headers="headers"
      :items="phenopackets"
      :loading="loading"
      :items-length="totalItems"
      :custom-sort="customSort"
      hide-default-footer
      class="elevation-1 clickable-rows"
      density="compact"
      @update:options="onOptionsUpdate"
      @click:row="handleRowClick"
    >
      <template #top>
        <v-toolbar flat>
          <v-toolbar-title>Phenopackets</v-toolbar-title>
          <v-spacer />
          <!-- Search Field -->
          <v-text-field
            v-model="searchQuery"
            label="Search"
            placeholder="Search across all phenopackets..."
            prepend-inner-icon="mdi-magnify"
            clearable
            hide-details
            density="compact"
            style="max-width: 350px"
            class="mr-2"
            @keyup.enter="applySearch"
            @click:clear="clearSearch"
          />
          <v-btn color="primary" :loading="loading" @click="applySearch"> Search </v-btn>
          <v-spacer class="mx-2" />
          <!-- Cursor pagination toggle -->
          <v-tooltip location="bottom">
            <template #activator="{ props }">
              <v-switch
                v-model="useCursorPagination"
                v-bind="props"
                label="Stable pagination"
                color="primary"
                hide-details
                density="compact"
                class="mr-4"
                @update:model-value="onPaginationModeChange"
              />
            </template>
            <span>
              Enable cursor pagination for stable results<br>
              (prevents duplicate/missing records when data changes)
            </span>
          </v-tooltip>
          <v-divider vertical class="mr-4" />
          <div class="d-flex align-center">
            <!-- Rows per page label and dropdown -->
            <span class="mr-2">Rows per page:</span>
            <v-select
              v-model="options.itemsPerPage"
              :items="itemsPerPageOptions"
              dense
              hide-details
              solo
              style="max-width: 120px"
            />
            <!-- Display the current items range -->
            <span class="mx-2">{{ rangeText }}</span>
            <!-- Pagination navigation buttons -->
            <v-btn icon :disabled="!canGoToFirst" @click="goToFirstPage">
              <v-icon>mdi-page-first</v-icon>
            </v-btn>
            <v-btn icon :disabled="!canGoToPrevious" @click="goToPreviousPage">
              <v-icon>mdi-chevron-left</v-icon>
            </v-btn>
            <v-btn icon :disabled="!canGoToNext" @click="goToNextPage">
              <v-icon>mdi-chevron-right</v-icon>
            </v-btn>
            <v-btn icon :disabled="!canGoToLast" @click="goToLastPage">
              <v-icon>mdi-page-last</v-icon>
            </v-btn>
          </div>
        </v-toolbar>
      </template>

      <!-- Render subject ID with chip -->
      <template #item.subject_id="{ item }">
        <v-chip color="teal-lighten-3" size="small" variant="flat">
          <v-icon left size="small">mdi-card-account-details</v-icon>
          {{ item.subject_id || 'N/A' }}
        </v-chip>
      </template>

      <!-- Render sex with chip -->
      <template #item.sex="{ item }">
        <v-chip :color="getSexChipColor(item.sex)" size="small" variant="flat">
          <v-icon left size="small">
            {{ getSexIcon(item.sex) }}
          </v-icon>
          {{ formatSex(item.sex) }}
        </v-chip>
      </template>

      <!-- Render primary disease -->
      <template #item.primary_disease="{ item }">
        <v-tooltip v-if="item.primary_disease" location="top">
          <template #activator="{ props }">
            <span
              v-bind="props"
              class="text-truncate"
              style="max-width: 200px; display: inline-block"
            >
              {{ item.primary_disease }}
            </span>
          </template>
          <span>{{ item.primary_disease }}</span>
        </v-tooltip>
        <span v-else>N/A</span>
      </template>

      <!-- Render phenotypes count with badge -->
      <template #item.features_count="{ item }">
        <v-chip
          :color="item.features_count > 0 ? 'green-lighten-3' : 'grey-lighten-2'"
          size="small"
          variant="flat"
        >
          {{ item.features_count }}
        </v-chip>
      </template>

      <!-- Render variants count with badge -->
      <template #item.variants_count="{ item }">
        <v-chip
          :color="item.variants_count > 0 ? 'blue-lighten-3' : 'grey-lighten-2'"
          size="small"
          variant="flat"
        >
          {{ item.variants_count }}
        </v-chip>
      </template>

      <template #no-data> No phenopackets found. </template>
    </v-data-table-server>
  </v-container>
</template>

<script>
import { getPhenopackets, searchPhenopackets } from '@/api';
import {
  buildSortParameter,
  buildPaginationParameters,
  buildCursorPaginationParameters,
  extractPaginationMeta,
} from '@/utils/pagination';
import { getSexIcon, getSexChipColor, formatSex } from '@/utils/sex';

export default {
  name: 'Phenopackets',
  data() {
    return {
      phenopackets: [],
      allPhenopackets: [], // Store all fetched phenopackets (used when no search active)
      loading: false,
      totalItems: 0,
      currentPage: 1,
      searchQuery: '', // Search query for backend full-text search
      useCursorPagination: false, // Toggle for cursor vs offset pagination
      paginationMeta: null, // Store pagination metadata (offset or cursor)
      currentCursor: null, // Current page cursor for cursor pagination
      paginationDirection: 'after', // Direction for cursor pagination ('after' or 'before')
      headers: [
        {
          title: 'Subject ID',
          value: 'subject_id',
          sortable: true,
          width: '180px',
        },
        {
          title: 'Sex',
          value: 'sex',
          sortable: true,
          width: '120px',
        },
        {
          title: 'Primary Disease',
          value: 'primary_disease',
          sortable: false,
          width: '220px',
        },
        {
          title: 'Phenotypes',
          value: 'features_count',
          sortable: false,
          width: '120px',
          align: 'center',
        },
        {
          title: 'Variants',
          value: 'variants_count',
          sortable: false,
          width: '100px',
          align: 'center',
        },
      ],
      options: {
        page: 1,
        itemsPerPage: 10,
        sortBy: [],
      },
      itemsPerPageOptions: [10, 20, 50, 100],
    };
  },
  computed: {
    totalPages() {
      if (this.useCursorPagination) {
        return 0; // Not available in cursor pagination
      }
      return Math.ceil(this.totalItems / this.options.itemsPerPage);
    },
    pageStart() {
      return (this.currentPage - 1) * this.options.itemsPerPage + 1;
    },
    pageEnd() {
      return Math.min(this.currentPage * this.options.itemsPerPage, this.totalItems);
    },
    rangeText() {
      if (this.useCursorPagination) {
        // Cursor pagination: show current page items count (page number not available)
        const itemCount = this.phenopackets.length;
        return `Current page (${itemCount} items)`;
      }
      // Offset pagination: show range
      return this.totalItems === 0
        ? '0 of 0'
        : `${this.pageStart}-${this.pageEnd} of ${this.totalItems}`;
    },
    canGoToPrevious() {
      if (this.useCursorPagination) {
        return this.paginationMeta?.hasPreviousPage || false;
      }
      return this.currentPage > 1;
    },
    canGoToNext() {
      if (this.useCursorPagination) {
        return this.paginationMeta?.hasNextPage || false;
      }
      return this.currentPage < this.totalPages;
    },
    canGoToFirst() {
      if (this.useCursorPagination) {
        // Can go to first if there's a previous page (meaning we're not on first page)
        return this.paginationMeta?.hasPreviousPage || false;
      }
      return this.currentPage > 1;
    },
    canGoToLast() {
      if (this.useCursorPagination) {
        return false; // Cannot jump to last with cursor pagination
      }
      return this.currentPage < this.totalPages;
    },
  },
  watch: {
    options: {
      handler() {
        this.fetchPhenopackets();
      },
      deep: true,
      immediate: true,
    },
  },
  methods: {
    async fetchPhenopackets() {
      this.loading = true;
      window.logService.debug('Starting phenopackets fetch', {
        currentPage: this.currentPage,
        itemsPerPage: this.options.itemsPerPage,
        sortBy: this.options.sortBy,
        useCursorPagination: this.useCursorPagination,
        hasSearchQuery: !!this.searchQuery,
      });

      try {
        const { itemsPerPage } = this.options;

        // If search query is active, use search API instead of regular list
        if (this.searchQuery && this.searchQuery.trim()) {
          await this.performSearch();
          return;
        }

        // Regular listing without search
        const { sortBy } = this.options;

        // Map frontend column keys to backend sort fields
        const sortFieldMap = {
          subject_id: 'subject_id',
          sex: 'subject_sex',
        };

        // Build sort parameter
        const sortParam = buildSortParameter(sortBy, sortFieldMap);

        // Build pagination parameters based on mode
        let paginationParams;
        if (this.useCursorPagination) {
          // Cursor pagination: use current cursor with direction
          paginationParams = buildCursorPaginationParameters(
            this.currentCursor,
            itemsPerPage,
            this.paginationDirection
          );
        } else {
          // Offset pagination: use page number
          paginationParams = buildPaginationParameters(this.currentPage, itemsPerPage);
        }

        // Fetch phenopackets using JSON:API parameters
        const response = await getPhenopackets({
          ...paginationParams,
          ...(sortParam && { sort: sortParam }),
        });

        // Extract JSON:API response structure
        const jsonApiData = response.data || {};
        const phenopacketDocuments = jsonApiData.data || [];
        const paginationMeta = extractPaginationMeta(response);

        window.logService.debug('JSON:API response received', {
          dataCount: phenopacketDocuments.length,
          pagination: paginationMeta,
          hasLinks: !!jsonApiData.links,
        });

        // Transform response data (phenopackets are already GA4GH format)
        this.allPhenopackets = phenopacketDocuments.map((pp) => this.transformPhenopacket(pp));
        this.phenopackets = this.allPhenopackets;

        window.logService.debug('Phenopackets data transformation complete', {
          rawDataCount: phenopacketDocuments.length,
          transformedCount: this.allPhenopackets.length,
          sampleStructure:
            this.allPhenopackets.length > 0 ? Object.keys(this.allPhenopackets[0]) : [],
        });

        // Store pagination metadata
        this.paginationMeta = paginationMeta;

        // Update UI state based on pagination type
        if (paginationMeta.type === 'cursor') {
          // Cursor pagination: totalItems not available, use hasNextPage for navigation
          this.totalItems = 0; // Not available in cursor pagination
        } else {
          // Offset pagination: use totalRecords
          this.totalItems = paginationMeta.totalRecords;
        }

        window.logService.info('Phenopackets fetched successfully', {
          count: phenopacketDocuments.length,
          ...paginationMeta,
        });
      } catch (error) {
        window.logService.error('Failed to fetch phenopackets', {
          error: error.message,
          status: error.response?.status,
          pagination: { page: this.currentPage, itemsPerPage: this.options.itemsPerPage },
        });
        this.phenopackets = [];
        this.totalItems = 0;
      } finally {
        this.loading = false;
      }
    },

    /**
     * Transform phenopacket JSONB to flat table row.
     * Extracts nested fields for display.
     * Input is now GA4GH Phenopacket v2 directly (from JSON:API data array)
     */
    transformPhenopacket(phenopacket) {
      const subject = phenopacket.subject || {};
      const diseases = phenopacket.diseases || [];
      const features = phenopacket.phenotypicFeatures || [];
      const interpretations = phenopacket.interpretations || [];

      // Count variants from interpretations
      let variantsCount = 0;
      interpretations.forEach((interp) => {
        const genomicInterps = interp.diagnosis?.genomicInterpretations || [];
        variantsCount += genomicInterps.length;
      });

      return {
        phenopacket_id: phenopacket.id,
        subject_id: subject.id || 'N/A',
        sex: subject.sex || 'UNKNOWN_SEX',
        primary_disease: diseases[0]?.term?.label || null,
        features_count: features.length,
        variants_count: variantsCount,
      };
    },

    onOptionsUpdate(newOptions) {
      const sortChanged =
        this.options.sortBy !== newOptions.sortBy || this.options.sortDesc !== newOptions.sortDesc;

      this.options = { ...newOptions };

      // Trigger server-side fetch when sorting changes
      if (sortChanged) {
        window.logService.info('Sort order changed', {
          sortBy: newOptions.sortBy,
          sortDesc: newOptions.sortDesc,
        });
        this.fetchPhenopackets();
      }
    },

    onPaginationModeChange(useCursor) {
      window.logService.info('Pagination mode changed', {
        mode: useCursor ? 'cursor' : 'offset',
      });
      // Reset pagination state when switching modes
      this.currentPage = 1;
      this.currentCursor = null;
      this.paginationDirection = 'after';
      this.paginationMeta = null;
      // Refetch with new mode
      this.fetchPhenopackets();
    },

    // Disable client-side sorting
    customSort(items) {
      return items;
    },

    goToFirstPage() {
      window.logService.debug('Pagination: navigating to first page');
      if (this.useCursorPagination) {
        // Reset cursor pagination
        this.currentCursor = null;
        this.paginationDirection = 'after';
      } else {
        this.currentPage = 1;
      }
      this.fetchPhenopackets();
    },

    goToPreviousPage() {
      if (this.useCursorPagination) {
        // Cursor pagination: use startCursor with page[before]
        if (this.paginationMeta?.hasPreviousPage) {
          window.logService.debug('Pagination: navigating to previous page (cursor)');
          // Use startCursor to go backwards
          this.currentCursor = this.paginationMeta.startCursor;
          this.paginationDirection = 'before';
          this.fetchPhenopackets();
        }
      } else {
        // Offset pagination
        if (this.currentPage > 1) {
          window.logService.debug('Pagination: navigating to previous page (offset)', {
            fromPage: this.currentPage,
            toPage: this.currentPage - 1,
          });
          this.currentPage--;
          this.fetchPhenopackets();
        }
      }
    },

    goToNextPage() {
      if (this.useCursorPagination) {
        // Cursor pagination: use endCursor with page[after]
        if (this.paginationMeta?.hasNextPage) {
          window.logService.debug('Pagination: navigating to next page (cursor)');
          this.currentCursor = this.paginationMeta.endCursor;
          this.paginationDirection = 'after';
          this.fetchPhenopackets();
        }
      } else {
        // Offset pagination
        if (this.currentPage < this.totalPages) {
          window.logService.debug('Pagination: navigating to next page (offset)', {
            fromPage: this.currentPage,
            toPage: this.currentPage + 1,
          });
          this.currentPage++;
          this.fetchPhenopackets();
        }
      }
    },

    goToLastPage() {
      if (this.useCursorPagination) {
        // Cursor pagination doesn't support jumping to last page
        window.logService.warn('Cannot jump to last page with cursor pagination');
        return;
      }
      window.logService.debug('Pagination: navigating to last page', {
        fromPage: this.currentPage,
        toPage: this.totalPages,
      });
      this.currentPage = this.totalPages;
      this.fetchPhenopackets();
    },

    // Sex formatting functions imported from @/utils/sex
    getSexIcon,
    getSexChipColor,
    formatSex,

    handleRowClick(event, { item }) {
      // Navigate to phenopacket detail page
      window.logService.info('Navigating to phenopacket detail', {
        phenopacketId: item.phenopacket_id,
        subjectId: item.subject_id,
      });
      this.$router.push(`/phenopackets/${item.phenopacket_id}`);
    },

    async performSearch() {
      const { itemsPerPage } = this.options;
      const skip = (this.currentPage - 1) * itemsPerPage;

      window.logService.debug('Performing backend search', {
        query: this.searchQuery,
        skip,
        limit: itemsPerPage,
      });

      try {
        const response = await searchPhenopackets({
          q: this.searchQuery.trim(),
          skip,
          limit: itemsPerPage,
        });

        // Extract search results
        const searchResults = response.data?.data || [];
        const totalResults = response.data?.meta?.total || 0;

        window.logService.debug('Search results received', {
          count: searchResults.length,
          total: totalResults,
        });

        // Transform search results (they're already phenopackets from attributes)
        this.phenopackets = searchResults.map((result) => {
          // result.attributes contains the phenopacket, result.id is the ID
          const phenopacket = result.attributes;
          return {
            ...this.transformPhenopacket(phenopacket),
            search_rank: result.meta?.search_rank, // Include relevance score if available
          };
        });

        this.allPhenopackets = this.phenopackets; // Store for consistency
        this.totalItems = totalResults;

        window.logService.info('Search completed successfully', {
          query: this.searchQuery,
          results: searchResults.length,
          total: totalResults,
        });
      } catch (error) {
        window.logService.error('Search failed', {
          error: error.message,
          status: error.response?.status,
          query: this.searchQuery,
        });
        this.phenopackets = [];
        this.totalItems = 0;
      }
    },

    applySearch() {
      // Trigger re-fetch with search query
      // Reset to first page when starting new search
      this.currentPage = 1;
      this.fetchPhenopackets();
    },

    clearSearch() {
      this.searchQuery = '';
      this.currentPage = 1;
      this.fetchPhenopackets(); // Re-fetch without search
      window.logService.info('Cleared phenopackets search');
    },
  },
};
</script>

<style scoped>
.font-weight-bold {
  font-weight: bold;
}

.text-truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Make table rows clickable with hover effect */
.clickable-rows :deep(tbody tr) {
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.clickable-rows :deep(tbody tr:hover) {
  background-color: rgba(0, 0, 0, 0.04);
}
</style>
