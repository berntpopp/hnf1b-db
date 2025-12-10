<!-- src/views/Phenopackets.vue -->
<!--
  Phenopacket Registry with server-side offset pagination following JSON:API v1.1 spec.

  Features:
  - Server-side pagination with page[number] and page[size]
  - Clickable page numbers for direct page navigation
  - Server-side sorting (subject_id, sex columns)
  - Sex filter (feature parity with Variants page)
  - Full-text search
-->
<template>
  <v-container fluid>
    <!-- Unified Table with Integrated Search Toolbar -->
    <AppDataTable
      v-model:options="options"
      :headers="headers"
      :items="phenopackets"
      :loading="loading"
      :items-length="phenopackets.length"
      :custom-sort="customSort"
      hide-default-footer
      title="Phenopacket Registry"
      @update:options="onOptionsUpdate"
      @click:row="handleRowClick"
    >
      <!-- Integrated Search Toolbar -->
      <template #toolbar>
        <AppTableToolbar
          v-model:search-query="searchQuery"
          search-placeholder="Search phenopackets..."
          :result-count="pagination.totalRecords"
          result-label="phenopackets"
          :loading="loading"
          @search="applySearch"
          @clear-search="clearSearch"
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
        <div class="d-flex align-center justify-space-between">
          <AppPagination
            :current-count="phenopackets.length"
            :current-page="pagination.currentPage"
            :page-size="pagination.pageSize"
            :total-pages="pagination.totalPages"
            :total-records="pagination.totalRecords"
            :items-per-page-options="itemsPerPageOptions"
            class="flex-grow-1"
            @go-to-page="goToPage"
            @update:page-size="onPageSizeChange"
          />
          <!-- Create Button - Curator/Admin only -->
          <div v-if="canCreatePhenopacket" class="d-flex align-center pr-4">
            <v-divider vertical class="mx-2" />
            <v-tooltip text="Create New" location="bottom" aria-label="Create new phenopacket">
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  icon="mdi-plus"
                  variant="text"
                  color="success"
                  size="small"
                  aria-label="Create new phenopacket"
                  @click="navigateToCreate"
                />
              </template>
            </v-tooltip>
          </div>
        </div>
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

      <!-- Column Header: Sex with filter menu -->
      <template #header.sex="{ column, getSortIcon, toggleSort, isSorted }">
        <ColumnHeaderFilter
          v-model="sexFilter"
          :title="column.title"
          :options="sexOptions"
          select-label="Select sex"
          filter-icon="mdi-gender-male-female"
          :sort-icon="isSorted(column) ? getSortIcon(column) : null"
          @sort="toggleSort(column)"
          @clear="clearFilter('sex')"
        />
      </template>

      <!-- Render subject ID with chip -->
      <template #item.subject_id="{ item }">
        <v-chip color="teal-lighten-3" size="x-small" variant="flat">
          <v-icon start size="x-small">mdi-card-account-details</v-icon>
          {{ item.subject_id || 'N/A' }}
        </v-chip>
      </template>

      <!-- Render sex with chip -->
      <template #item.sex="{ item }">
        <v-chip :color="getSexChipColor(item.sex)" size="x-small" variant="flat">
          <v-icon start size="x-small">{{ getSexIcon(item.sex) }}</v-icon>
          {{ formatSex(item.sex) }}
        </v-chip>
      </template>

      <!-- Render phenotypes count with badge -->
      <template #item.features_count="{ item }">
        <v-chip
          :color="item.features_count > 0 ? 'green-lighten-3' : 'grey-lighten-2'"
          size="x-small"
          variant="flat"
        >
          {{ item.features_count }}
        </v-chip>
      </template>

      <!-- Render has variant column -->
      <template #item.has_variant="{ item }">
        <v-chip
          :color="item.has_variant ? 'green-lighten-3' : 'grey-lighten-2'"
          size="x-small"
          variant="flat"
        >
          <v-icon start size="x-small">
            {{ item.has_variant ? 'mdi-dna' : 'mdi-minus' }}
          </v-icon>
          {{ item.has_variant ? 'Yes' : 'No' }}
        </v-chip>
      </template>

      <template #no-data>
        <span class="text-body-2 text-medium-emphasis">No phenopackets found.</span>
      </template>
    </AppDataTable>
  </v-container>
</template>

<script>
import { getPhenopackets, searchPhenopackets } from '@/api';
import { buildSortParameter, extractPaginationMeta } from '@/utils/pagination';
import { getSexIcon, getSexChipColor, formatSex } from '@/utils/sex';
import { useAuthStore } from '@/stores/authStore';
import { useTableUrlState } from '@/composables/useTableUrlState';
import AppDataTable from '@/components/common/AppDataTable.vue';
import AppTableToolbar from '@/components/common/AppTableToolbar.vue';
import AppPagination from '@/components/common/AppPagination.vue';
import ColumnHeaderFilter from '@/components/common/ColumnHeaderFilter.vue';

export default {
  name: 'Phenopackets',
  components: {
    AppDataTable,
    AppTableToolbar,
    AppPagination,
    ColumnHeaderFilter,
  },
  setup() {
    // URL state synchronization
    // Return entire urlState to preserve ref reactivity in Options API
    const urlState = useTableUrlState({
      defaultPageSize: 10,
      defaultSort: null,
      filters: { sex: null },
    });

    return { urlState };
  },
  data() {
    return {
      phenopackets: [],
      loading: false,

      // Sex filter options (GA4GH Phenopackets v2 enum values)
      sexOptions: [
        { title: 'Male', value: 'MALE' },
        { title: 'Female', value: 'FEMALE' },
        { title: 'Other', value: 'OTHER_SEX' },
        { title: 'Unknown', value: 'UNKNOWN_SEX' },
      ],

      // Offset pagination state (synced from URL)
      pagination: {
        currentPage: 1,
        pageSize: 10,
        totalPages: 0,
        totalRecords: 0,
      },

      // Table configuration
      // features_count is now server-side sortable via generated column
      headers: [
        { title: 'Subject ID', value: 'subject_id', sortable: true, width: '160px' },
        { title: 'Sex', value: 'sex', sortable: true, width: '100px' },
        {
          title: 'Phenotypes',
          value: 'features_count',
          sortable: true,
          width: '100px',
          align: 'center',
        },
        { title: 'Has Variant', value: 'has_variant', sortable: true, width: '120px' },
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
    // Bridge URL state to component properties for v-model bindings
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
    // Direct computed for sex filter - v-model compatible
    sexFilter: {
      get() {
        return this.urlState?.filters?.sex?.value ?? null;
      },
      set(value) {
        if (this.urlState?.filters?.sex) {
          this.urlState.filters.sex.value = value;
        }
      },
    },
    // Keep filterValues for compatibility but read-only
    filterValues() {
      return {
        sex: this.urlState?.filters?.sex?.value ?? null,
      };
    },
    canCreatePhenopacket() {
      const authStore = useAuthStore();
      const userRole = authStore.user?.role;
      return userRole === 'curator' || userRole === 'admin';
    },
    hasActiveFilters() {
      return (this.urlState?.activeFilterCount?.value ?? 0) > 0;
    },
    activeFilterCount() {
      return this.urlState?.activeFilterCount?.value ?? 0;
    },
  },
  watch: {
    options: {
      handler(newVal, oldVal) {
        // Sync sort to URL and fetch
        if (oldVal && JSON.stringify(newVal.sortBy) !== JSON.stringify(oldVal.sortBy)) {
          this.syncSortToUrl();
          this.urlState.resetPage();
          this.fetchPhenopackets();
        }
      },
      deep: true,
    },
    // Watch URL state changes for page
    'urlState.page.value': {
      handler(newVal) {
        if (this.pagination.currentPage !== newVal) {
          this.pagination.currentPage = newVal;
          this.fetchPhenopackets();
        }
      },
      immediate: true,
    },
    // Watch URL state changes for pageSize
    'urlState.pageSize.value': {
      handler(newVal) {
        if (this.pagination.pageSize !== newVal) {
          this.pagination.pageSize = newVal;
          this.fetchPhenopackets();
        }
      },
      immediate: true,
    },
    // Watch URL state changes for search
    'urlState.search.value': {
      handler() {
        this.fetchPhenopackets();
      },
    },
    // Watch URL state changes for sex filter
    'urlState.filters.sex.value': {
      handler() {
        this.urlState.resetPage();
        this.fetchPhenopackets();
      },
    },
  },
  mounted() {
    // Initial fetch with URL state
    this.syncPaginationFromUrl();
    this.fetchPhenopackets();
  },
  methods: {
    syncPaginationFromUrl() {
      // Sync pagination state from URL refs
      this.pagination.currentPage = this.urlState?.page?.value ?? 1;
      this.pagination.pageSize = this.urlState?.pageSize?.value ?? 10;
    },

    syncSortToUrl() {
      // Sync current sort state to URL
      const { sortBy } = this.options;
      const sortFieldMap = {
        subject_id: 'subject_id',
        sex: 'subject_sex',
        features_count: 'features_count',
        has_variant: 'has_variant',
      };
      const sortParam = buildSortParameter(sortBy, sortFieldMap);
      if (this.urlState?.sort) {
        this.urlState.sort.value = sortParam || null;
      }
    },

    async fetchPhenopackets() {
      this.loading = true;
      const searchValue = this.urlState?.search?.value ?? '';
      window.logService.debug('Fetching phenopackets', {
        page: this.pagination.currentPage,
        search: !!searchValue,
      });

      try {
        if (searchValue?.trim()) {
          await this.performSearch();
          return;
        }

        const { sortBy } = this.options;
        // Updated sort field map with new columns
        const sortFieldMap = {
          subject_id: 'subject_id',
          sex: 'subject_sex',
          features_count: 'features_count',
          has_variant: 'has_variant',
        };
        const sortParam = buildSortParameter(sortBy, sortFieldMap);

        // Build offset pagination parameters from URL state
        const paginationParams = {
          'page[number]': this.urlState?.page?.value ?? 1,
          'page[size]': this.urlState?.pageSize?.value ?? 10,
        };

        // Get sex filter from URL state
        const sexFilter = this.urlState?.filters?.sex?.value;

        const response = await getPhenopackets({
          ...paginationParams,
          ...(sortParam && { sort: sortParam }),
          ...(sexFilter && { 'filter[sex]': sexFilter }),
        });

        const jsonApiData = response.data || {};
        const phenopacketDocuments = jsonApiData.data || [];
        const meta = extractPaginationMeta(response);

        this.phenopackets = phenopacketDocuments.map((pp) => this.transformPhenopacket(pp));
        this.pagination.currentPage = meta.currentPage;
        this.pagination.totalPages = meta.totalPages;
        this.pagination.totalRecords = meta.totalRecords;

        window.logService.info('Phenopackets fetched', {
          count: phenopacketDocuments.length,
          page: meta.currentPage,
          totalPages: meta.totalPages,
          totalRecords: meta.totalRecords,
        });
      } catch (error) {
        window.logService.error('Failed to fetch phenopackets', { error: error.message });
        this.phenopackets = [];
      } finally {
        this.loading = false;
      }
    },

    transformPhenopacket(phenopacket) {
      const subject = phenopacket.subject || {};
      const features = phenopacket.phenotypicFeatures || [];
      const interpretations = phenopacket.interpretations || [];

      const presentFeaturesCount = features.filter((f) => !f.excluded).length;

      let variantDisplay = null;
      let variantFull = null;
      let variantType = null;

      if (interpretations.length > 0) {
        const genomicInterps = interpretations[0].diagnosis?.genomicInterpretations || [];
        if (genomicInterps.length > 0) {
          const variantInterp = genomicInterps[0].variantInterpretation || {};
          const varDescriptor = variantInterp.variationDescriptor || {};
          const variantId = varDescriptor.id || '';
          const label = varDescriptor.label || '';
          const expressions = varDescriptor.expressions || [];
          const extensions = varDescriptor.extensions || [];

          const isCNV = variantId.includes('DEL') || variantId.includes('DUP');
          variantType = isCNV ? 'CNV' : 'SNV';

          const hgvsC = expressions.find((e) => e.syntax === 'hgvs.c');

          if (isCNV) {
            const coordsExt = extensions.find((e) => e.name === 'coordinates');
            const lengthBp = coordsExt?.value?.length;
            if (lengthBp) {
              const lengthMb = (lengthBp / 1000000).toFixed(2);
              variantDisplay = `CNV (${lengthMb} Mb)`;
            } else {
              variantDisplay = 'CNV';
            }
            variantFull = label || variantId;
          } else if (hgvsC) {
            const hgvsValue = hgvsC.value || '';
            const cNotation = hgvsValue.includes(':') ? hgvsValue.split(':')[1] : hgvsValue;
            variantDisplay = cNotation;
            variantFull = hgvsValue;
          } else {
            variantDisplay = label || variantId;
            variantFull = label || variantId;
          }
        }
      }

      return {
        phenopacket_id: phenopacket.id,
        subject_id: subject.id || 'N/A',
        sex: subject.sex || 'UNKNOWN_SEX',
        features_count: presentFeaturesCount,
        has_variant: interpretations.length > 0,
        variant_display: variantDisplay,
        variant_full: variantFull,
        variant_type: variantType,
      };
    },

    onOptionsUpdate(newOptions) {
      this.options = { ...newOptions };
    },

    onPageSizeChange(newSize) {
      // Update URL state which triggers watch and fetch
      if (this.urlState?.pageSize) {
        this.urlState.pageSize.value = newSize;
      }
      this.urlState.resetPage();
      this.pagination.pageSize = newSize;
      this.pagination.currentPage = 1;
      this.fetchPhenopackets();
    },

    customSort(items) {
      return items;
    },

    goToPage(page) {
      if (page < 1 || page > this.pagination.totalPages) return;
      // Update URL state
      if (this.urlState?.page) {
        this.urlState.page.value = page;
      }
      this.pagination.currentPage = page;
      this.fetchPhenopackets();
    },

    getSexIcon,
    getSexChipColor,
    formatSex,

    navigateToCreate() {
      this.$router.push('/phenopackets/create');
    },

    handleRowClick(event, { item }) {
      window.logService.info('Navigating to phenopacket', { id: item.phenopacket_id });
      this.$router.push(`/phenopackets/${item.phenopacket_id}`);
    },

    async performSearch() {
      try {
        const paginationParams = {
          'page[number]': this.pagination.currentPage,
          'page[size]': this.pagination.pageSize,
        };

        const response = await searchPhenopackets({
          q: this.searchQuery.trim(),
          ...paginationParams,
        });

        const searchResults = response.data?.data || [];
        const meta = extractPaginationMeta(response);

        this.phenopackets = searchResults.map((result) => {
          const phenopacket = result.attributes;
          return {
            ...this.transformPhenopacket(phenopacket),
            search_rank: result.meta?.search_rank,
          };
        });

        this.pagination.currentPage = meta.currentPage;
        this.pagination.totalPages = meta.totalPages;
        this.pagination.totalRecords = meta.totalRecords;

        window.logService.info('Search completed', {
          query: this.searchQuery,
          results: searchResults.length,
          totalRecords: meta.totalRecords,
        });
      } catch (error) {
        window.logService.error('Search failed', { error: error.message });
        this.phenopackets = [];
      } finally {
        this.loading = false;
      }
    },

    applySearch() {
      this.urlState.resetPage();
      this.pagination.currentPage = 1;
      this.fetchPhenopackets();
    },

    clearSearch() {
      // Clear URL search state
      if (this.urlState?.search) {
        this.urlState.search.value = '';
      }
      this.urlState.resetPage();
      this.pagination.currentPage = 1;
      this.fetchPhenopackets();
    },

    clearFilter(key) {
      // Clear filter via URL state
      this.urlState.clearFilter(key);
    },

    clearAllFilters() {
      // Clear all filters via URL state
      this.urlState.clearAllFilters();
      this.pagination.currentPage = 1;
      this.fetchPhenopackets();
    },
  },
};
</script>

<style scoped>
:deep(tbody tr) {
  cursor: pointer;
}
</style>
