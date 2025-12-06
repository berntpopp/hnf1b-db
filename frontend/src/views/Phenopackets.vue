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
            <v-tooltip text="Create New" location="bottom">
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  icon="mdi-plus"
                  variant="text"
                  color="success"
                  size="small"
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
        <div class="d-flex align-center justify-space-between header-wrapper">
          <div class="d-flex align-center flex-grow-1 sortable-header" @click="toggleSort(column)">
            <span class="header-title">{{ column.title }}</span>
            <v-icon v-if="isSorted(column)" size="small" class="ml-1">{{
              getSortIcon(column)
            }}</v-icon>
          </div>
          <v-menu :close-on-content-click="false" location="bottom">
            <template #activator="{ props }">
              <v-btn
                icon
                size="x-small"
                variant="text"
                v-bind="props"
                :color="filterValues.sex ? 'primary' : 'default'"
              >
                <v-icon size="small">
                  {{ filterValues.sex ? 'mdi-filter' : 'mdi-filter-outline' }}
                </v-icon>
              </v-btn>
            </template>
            <v-card min-width="200" max-width="280">
              <v-card-title class="text-subtitle-2 py-2 d-flex align-center">
                <v-icon size="small" class="mr-2">mdi-gender-male-female</v-icon>
                Filter: Sex
              </v-card-title>
              <v-divider />
              <v-card-text class="pa-3">
                <v-select
                  v-model="filterValues.sex"
                  :items="sexOptions"
                  label="Select sex"
                  density="compact"
                  variant="outlined"
                  clearable
                  hide-details
                />
              </v-card-text>
              <v-divider />
              <v-card-actions class="pa-2">
                <v-spacer />
                <v-btn size="small" variant="text" @click="clearFilter('sex')">Clear</v-btn>
              </v-card-actions>
            </v-card>
          </v-menu>
        </div>
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

      <!-- Render variant display -->
      <template #item.variant_display="{ item }">
        <v-tooltip v-if="item.variant_display" location="top">
          <template #activator="{ props }">
            <v-chip
              v-bind="props"
              :color="item.variant_type === 'CNV' ? 'purple-lighten-3' : 'blue-lighten-3'"
              size="x-small"
              variant="flat"
              class="text-truncate"
              style="max-width: 180px"
            >
              {{ item.variant_display }}
            </v-chip>
          </template>
          <span>{{ item.variant_full }}</span>
        </v-tooltip>
        <span v-else class="text-body-2 text-medium-emphasis">N/A</span>
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
import AppDataTable from '@/components/common/AppDataTable.vue';
import AppTableToolbar from '@/components/common/AppTableToolbar.vue';
import AppPagination from '@/components/common/AppPagination.vue';

export default {
  name: 'Phenopackets',
  components: {
    AppDataTable,
    AppTableToolbar,
    AppPagination,
  },
  data() {
    return {
      phenopackets: [],
      loading: false,
      searchQuery: '',

      // Filter state (feature parity with Variants page)
      filterValues: {
        sex: null,
      },

      // Sex filter options (GA4GH Phenopackets v2 enum values)
      sexOptions: [
        { title: 'Male', value: 'MALE' },
        { title: 'Female', value: 'FEMALE' },
        { title: 'Other', value: 'OTHER_SEX' },
        { title: 'Unknown', value: 'UNKNOWN_SEX' },
      ],

      // Offset pagination state
      pagination: {
        currentPage: 1,
        pageSize: 10,
        totalPages: 0,
        totalRecords: 0,
      },

      // Table configuration
      // Note: features_count and variant_display are computed client-side
      // and cannot be sorted server-side
      headers: [
        { title: 'Subject ID', value: 'subject_id', sortable: true, width: '160px' },
        { title: 'Sex', value: 'sex', sortable: true, width: '100px' },
        {
          title: 'Phenotypes',
          value: 'features_count',
          sortable: false,
          width: '100px',
          align: 'center',
        },
        { title: 'Variant', value: 'variant_display', sortable: false, width: '200px' },
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
    canCreatePhenopacket() {
      const authStore = useAuthStore();
      const userRole = authStore.user?.role;
      return userRole === 'curator' || userRole === 'admin';
    },
    hasActiveFilters() {
      return !!(this.searchQuery || this.filterValues.sex);
    },
    activeFilterCount() {
      let count = 0;
      if (this.searchQuery) count++;
      if (this.filterValues.sex) count++;
      return count;
    },
  },
  watch: {
    options: {
      handler(newVal, oldVal) {
        // Only fetch if sort changed (not on initial load which is handled separately)
        if (oldVal && JSON.stringify(newVal.sortBy) !== JSON.stringify(oldVal.sortBy)) {
          this.pagination.currentPage = 1;
          this.fetchPhenopackets();
        }
      },
      deep: true,
    },
    filterValues: {
      handler() {
        this.pagination.currentPage = 1;
        this.fetchPhenopackets();
      },
      deep: true,
    },
  },
  mounted() {
    this.fetchPhenopackets();
  },
  methods: {
    async fetchPhenopackets() {
      this.loading = true;
      window.logService.debug('Fetching phenopackets', {
        page: this.pagination.currentPage,
        search: !!this.searchQuery,
      });

      try {
        if (this.searchQuery?.trim()) {
          await this.performSearch();
          return;
        }

        const { sortBy } = this.options;
        const sortFieldMap = { subject_id: 'subject_id', sex: 'subject_sex' };
        const sortParam = buildSortParameter(sortBy, sortFieldMap);

        // Build offset pagination parameters
        const paginationParams = {
          'page[number]': this.pagination.currentPage,
          'page[size]': this.pagination.pageSize,
        };

        const response = await getPhenopackets({
          ...paginationParams,
          ...(sortParam && { sort: sortParam }),
          ...(this.filterValues.sex && { 'filter[sex]': this.filterValues.sex }),
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
        variant_display: variantDisplay,
        variant_full: variantFull,
        variant_type: variantType,
      };
    },

    onOptionsUpdate(newOptions) {
      this.options = { ...newOptions };
    },

    onPageSizeChange(newSize) {
      this.pagination.pageSize = newSize;
      this.pagination.currentPage = 1;
      this.fetchPhenopackets();
    },

    customSort(items) {
      return items;
    },

    goToPage(page) {
      if (page < 1 || page > this.pagination.totalPages) return;
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
      this.pagination.currentPage = 1;
      this.fetchPhenopackets();
    },

    clearSearch() {
      this.searchQuery = '';
      this.pagination.currentPage = 1;
      this.fetchPhenopackets();
    },

    clearFilter(key) {
      this.filterValues[key] = null;
    },

    clearAllFilters() {
      this.searchQuery = '';
      this.filterValues = { sex: null };
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
