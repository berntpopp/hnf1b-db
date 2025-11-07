<!-- src/views/Variants.vue -->
<template>
  <v-container fluid>
    <!-- Search and Filter Section -->
    <v-card class="mb-4">
      <v-card-title>Search Variants</v-card-title>
      <v-card-text>
        <v-row>
          <!-- Text Search -->
          <v-col cols="12" md="4">
            <v-text-field
              v-model="searchQuery"
              label="Search"
              placeholder="Enter HGVS notation, gene symbol, or variant ID"
              prepend-inner-icon="mdi-magnify"
              clearable
              :loading="loading"
              hide-details
              @input="debouncedSearch"
              @click:clear="clearSearch"
            >
              <template #append-inner>
                <v-menu>
                  <template #activator="{ props }">
                    <v-btn
                      icon="mdi-help-circle-outline"
                      variant="text"
                      size="small"
                      v-bind="props"
                    />
                  </template>
                  <v-list density="compact">
                    <v-list-item>
                      <v-list-item-title class="font-weight-bold text-caption">
                        Search Examples:
                      </v-list-item-title>
                    </v-list-item>
                    <v-list-item>
                      <v-list-item-subtitle class="text-caption">
                        c.1654-2A>T (transcript)
                      </v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <v-list-item-subtitle class="text-caption">
                        p.Ser546Phe (protein)
                      </v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <v-list-item-subtitle class="text-caption">
                        Var1 (variant ID)
                      </v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <v-list-item-subtitle class="text-caption">
                        chr17:36098063 (coordinates)
                      </v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-menu>
              </template>
            </v-text-field>
          </v-col>

          <!-- Variant Type Filter -->
          <v-col cols="12" md="2">
            <v-select
              v-model="filterType"
              :items="variantTypes"
              label="Type"
              clearable
              :disabled="loading"
              hide-details
              @update:model-value="applyFilters"
            />
          </v-col>

          <!-- Classification Filter -->
          <v-col cols="12" md="2">
            <v-select
              v-model="filterClassification"
              :items="classifications"
              label="Classification"
              clearable
              :disabled="loading"
              hide-details
              @update:model-value="applyFilters"
            />
          </v-col>

          <!-- Molecular Consequence Filter -->
          <v-col cols="12" md="4">
            <v-select
              v-model="filterConsequence"
              :items="consequences"
              label="Consequence"
              clearable
              :disabled="loading"
              hide-details
              @update:model-value="applyFilters"
            />
          </v-col>
        </v-row>

        <!-- Active Filters Display -->
        <v-row v-if="hasActiveFilters" class="mt-2">
          <v-col cols="12">
            <v-chip-group>
              <v-chip
                v-if="searchQuery"
                closable
                color="primary"
                size="small"
                variant="flat"
                @click:close="clearSearch"
              >
                <v-icon start size="small"> mdi-magnify </v-icon>
                Search: {{ searchQuery }}
              </v-chip>
              <v-chip
                v-if="filterType"
                closable
                color="secondary"
                size="small"
                variant="flat"
                @click:close="clearTypeFilter"
              >
                <v-icon start size="small"> mdi-dna </v-icon>
                Type: {{ filterType }}
              </v-chip>
              <v-chip
                v-if="filterClassification"
                closable
                :color="getClassificationColor(filterClassification)"
                size="small"
                variant="flat"
                @click:close="clearClassificationFilter"
              >
                <v-icon start size="small"> mdi-alert-circle </v-icon>
                {{ filterClassification }}
              </v-chip>
              <v-chip
                v-if="filterConsequence"
                closable
                color="purple"
                size="small"
                variant="flat"
                @click:close="clearConsequenceFilter"
              >
                <v-icon start size="small"> mdi-molecule </v-icon>
                {{ filterConsequence }}
              </v-chip>
              <v-chip color="error" size="small" variant="outlined" @click="clearAllFilters">
                <v-icon start size="small"> mdi-close </v-icon>
                Clear All
              </v-chip>
            </v-chip-group>
          </v-col>
        </v-row>

        <!-- Results Count -->
        <v-row class="mt-1">
          <v-col cols="12">
            <div class="d-flex align-center">
              <v-chip color="info" size="small" variant="flat">
                <v-icon start size="small"> mdi-filter </v-icon>
                {{ filteredCount }} variants
                <span v-if="hasActiveFilters"> (filtered)</span>
              </v-chip>
              <v-spacer />
              <v-btn
                v-if="hasActiveFilters"
                variant="text"
                size="small"
                color="primary"
                @click="clearAllFilters"
              >
                <v-icon start> mdi-refresh </v-icon>
                Reset Filters
              </v-btn>
            </div>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Variants Table -->
    <v-data-table-server
      v-model:options="options"
      :headers="headers"
      :items="variants"
      :loading="loading"
      :items-length="totalPages"
      :custom-sort="customSort"
      hide-default-footer
      class="elevation-1"
      density="compact"
      @update:options="onOptionsUpdate"
      @click:row="handleRowClick"
    >
      <template #top>
        <v-toolbar flat>
          <v-toolbar-title>Variants</v-toolbar-title>
          <v-spacer />
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
            <v-btn icon :disabled="options.page === 1" @click="goToFirstPage">
              <v-icon>mdi-page-first</v-icon>
            </v-btn>
            <v-btn icon :disabled="options.page === 1" @click="goToPreviousPage">
              <v-icon>mdi-chevron-left</v-icon>
            </v-btn>
            <v-btn icon :disabled="options.page === totalPages" @click="goToNextPage">
              <v-icon>mdi-chevron-right</v-icon>
            </v-btn>
            <v-btn icon :disabled="options.page === totalPages" @click="goToLastPage">
              <v-icon>mdi-page-last</v-icon>
            </v-btn>
          </div>
        </v-toolbar>
      </template>

      <!-- Render simple_id as a clickable chip -->
      <template #item.simple_id="{ item }">
        <v-chip color="pink-lighten-3" class="ma-1" size="small" variant="flat">
          {{ item.simple_id }}
          <v-icon right> mdi-dna </v-icon>
        </v-chip>
      </template>

      <!-- Render transcript with only c. notation (strip NM_ prefix) -->
      <template #item.transcript="{ item }">
        {{ extractCNotation(item.transcript) }}
      </template>

      <!-- Render protein with only p. notation (strip NP_ prefix) -->
      <template #item.protein="{ item }">
        {{ extractPNotation(item.protein) }}
      </template>

      <!-- Render variant type with color coding -->
      <template #item.variant_type="{ item }">
        <v-chip
          :color="getVariantTypeColor(getVariantType(item))"
          class="ma-1"
          size="small"
          variant="flat"
        >
          {{ getVariantType(item) }}
        </v-chip>
      </template>

      <!-- Render HG38 with truncation for long values -->
      <template #item.hg38="{ item }">
        <v-tooltip v-if="item.hg38 && item.hg38.length > 40" location="top">
          <template #activator="{ props }">
            <span
              v-bind="props"
              class="text-truncate d-inline-block"
              style="max-width: 280px; cursor: help"
            >
              {{ item.hg38 }}
            </span>
          </template>
          <span style="word-break: break-all; max-width: 500px; display: block">{{
            item.hg38
          }}</span>
        </v-tooltip>
        <span v-else>{{ item.hg38 || '-' }}</span>
      </template>

      <!-- Render classification with color coding -->
      <template #item.classificationVerdict="{ item }">
        <v-chip
          v-if="item.classificationVerdict"
          :color="getPathogenicityColor(item.classificationVerdict)"
          class="ma-1"
          size="small"
          variant="flat"
        >
          {{ item.classificationVerdict }}
        </v-chip>
        <span v-else>-</span>
      </template>

      <!-- Render individual count as a badge -->
      <template #item.individualCount="{ item }">
        <v-chip color="light-green-lighten-3" class="ma-1" size="small" variant="flat">
          {{ item.individualCount || 0 }}
        </v-chip>
      </template>

      <!-- Custom header for Variant Type with cycle sort -->
      <template #header.variant_type="{ column }">
        <div
          class="d-flex align-center"
          style="cursor: pointer; user-select: none"
          @click="cycleVariantTypeSort"
        >
          <span>{{ column.title }}</span>
          <v-chip v-if="variantTypeSortPriority" size="x-small" color="primary" class="ml-1">
            {{ variantTypeSortPriority }}
          </v-chip>
        </div>
      </template>

      <!-- Custom header for Classification with cycle sort -->
      <template #header.classificationVerdict="{ column }">
        <div
          class="d-flex align-center"
          style="cursor: pointer; user-select: none"
          @click="cycleClassificationSort"
        >
          <span>{{ column.title }}</span>
          <v-chip v-if="classificationSortPriority" size="x-small" color="primary" class="ml-1">
            {{ classificationSortPriority }}
          </v-chip>
        </div>
      </template>

      <template #no-data>
        <v-empty-state
          v-if="hasActiveFilters"
          icon="mdi-filter-off"
          title="No variants found"
          text="No variants match your search criteria. Try adjusting your filters or clearing them."
        >
          <template #actions>
            <v-btn color="primary" @click="clearAllFilters"> Clear Filters </v-btn>
          </template>
        </v-empty-state>
        <span v-else>No variants found.</span>
      </template>
    </v-data-table-server>
  </v-container>
</template>

<script>
import debounce from 'just-debounce-it';
import { getVariants } from '@/api';
import { extractCNotation, extractPNotation } from '@/utils/hgvs';
import { getPathogenicityColor, getVariantTypeColor } from '@/utils/colors';
import { getVariantType } from '@/utils/variants';
import { API_CONFIG } from '@/config/app';

export default {
  name: 'Variants',
  data() {
    return {
      // Search and filter state
      searchQuery: '',
      filterType: null,
      filterClassification: null,
      filterConsequence: null,

      // Table data
      variants: [],
      loading: false,
      totalItems: 0,
      totalPages: 0,
      filteredCount: 0,

      // Initialization flag to prevent double loading
      // See: https://github.com/vuetifyjs/vuetify/issues/16878
      loadingInitialized: false,

      // Filter options
      variantTypes: ['SNV', 'insertion', 'indel', 'deletion', 'duplication'],
      classifications: [
        'PATHOGENIC',
        'LIKELY_PATHOGENIC',
        'UNCERTAIN_SIGNIFICANCE',
        'LIKELY_BENIGN',
        'BENIGN',
      ],

      // Cycle sorting state
      variantTypeCycleIndex: -1, // -1 means no cycle sort active
      classificationCycleIndex: -1, // -1 means no cycle sort active
      variantTypeSortPriority: null, // Selected type to show on top
      classificationSortPriority: null, // Selected classification to show on top
      consequences: [
        'Frameshift',
        'Nonsense',
        'Missense',
        'Splice Donor',
        'Splice Acceptor',
        'In-frame Deletion',
        'In-frame Insertion',
      ],

      // Table configuration
      headers: [
        {
          title: 'Variant ID',
          value: 'simple_id',
          sortable: true,
          width: '120px',
          headerProps: {
            class: 'font-weight-bold',
          },
        },
        {
          title: 'Transcript (c.)',
          value: 'transcript',
          sortable: true,
          width: '200px',
          headerProps: {
            class: 'font-weight-bold',
          },
        },
        {
          title: 'Protein (p.)',
          value: 'protein',
          sortable: true,
          width: '200px',
          headerProps: {
            class: 'font-weight-bold',
          },
        },
        {
          title: 'Variant Type',
          value: 'variant_type',
          sortable: true,
          width: '130px',
          headerProps: {
            class: 'font-weight-bold',
          },
        },
        {
          title: 'HG38',
          value: 'hg38',
          sortable: true,
          width: '280px',
          headerProps: {
            class: 'font-weight-bold',
          },
        },
        {
          title: 'Classification',
          value: 'classificationVerdict',
          sortable: true,
          width: '180px',
          headerProps: {
            class: 'font-weight-bold',
          },
        },
        {
          title: 'Individuals',
          value: 'individualCount',
          sortable: true,
          width: '120px',
          align: 'center',
          headerProps: {
            class: 'font-weight-bold',
          },
        },
      ],

      // Pagination options
      options: {
        page: 1,
        itemsPerPage: 10,
        sortBy: [{ key: 'simple_id', order: 'desc' }], // Default: sort by Variant ID descending
      },
      itemsPerPageOptions: [10, 20, 50, 100],
    };
  },
  computed: {
    // Check if any filters are active
    hasActiveFilters() {
      return !!(
        this.searchQuery ||
        this.filterType ||
        this.filterClassification ||
        this.filterConsequence
      );
    },

    // Calculate the starting item index for the current page
    pageStart() {
      return (this.options.page - 1) * this.options.itemsPerPage + 1;
    },

    // Calculate the ending item index for the current page
    pageEnd() {
      return Math.min(this.options.page * this.options.itemsPerPage, this.totalItems);
    },

    // Create the range text (e.g., "1-10 of 160")
    rangeText() {
      return this.totalItems === 0
        ? '0 of 0'
        : `${this.pageStart}-${this.pageEnd} of ${this.totalItems}`;
    },
  },
  watch: {
    // Fetch data whenever pagination or sorting options change
    // IMPORTANT: Do NOT use immediate:true here to prevent double loading
    // The v-data-table-server component calls @update:options on mount,
    // which triggers fetchVariants() through onOptionsUpdate()
    // Using immediate:true would cause fetchVariants() to be called twice:
    // 1. On component creation (immediate:true)
    // 2. On mount when table initializes (@update:options event)
    // See: https://github.com/vuetifyjs/vuetify/issues/16878
    options: {
      handler() {
        // Only fetch if initialization has completed
        if (this.loadingInitialized) {
          this.fetchVariants();
        }
      },
      deep: true,
    },
  },
  created() {
    // Debounce search to prevent excessive API calls (300ms delay)
    this.debouncedSearch = debounce(this.searchVariants, 300);
  },
  methods: {
    async fetchVariants() {
      this.loading = true;
      window.logService.debug('Starting variant fetch', {
        page: this.options.page,
        itemsPerPage: this.options.itemsPerPage,
        activeFilters: {
          searchQuery: this.searchQuery,
          filterType: this.filterType,
          filterClassification: this.filterClassification,
          filterConsequence: this.filterConsequence,
        },
        sortBy: this.options.sortBy,
      });

      try {
        const { page, itemsPerPage, sortBy } = this.options;
        let sortParam = '';
        if (Array.isArray(sortBy) && sortBy.length > 0) {
          // Expect sortBy[0] in the form: { key: 'fieldName', order: 'asc' } or { key: 'fieldName', order: 'desc' }
          const { key, order } = sortBy[0];
          sortParam = (order === 'desc' ? '-' : '') + key;
        }

        // Build request params with search and filters
        const requestParams = {
          sort: sortParam,
        };

        // When priority sorting is active, fetch ALL variants to sort them properly across pages
        // ⚠️ WARNING: This assumes database has fewer variants than MAX_VARIANTS_FOR_PRIORITY_SORT
        // If database grows beyond this limit, priority sorting will only work on first N variants
        // See @/config/app.js API_CONFIG.MAX_VARIANTS_FOR_PRIORITY_SORT for details and solutions
        if (this.variantTypeSortPriority || this.classificationSortPriority) {
          requestParams.page = 1;
          requestParams.page_size = API_CONFIG.MAX_VARIANTS_FOR_PRIORITY_SORT;
        } else {
          requestParams.page = page;
          requestParams.page_size = itemsPerPage;
        }

        // Add search query if present
        if (this.searchQuery) {
          requestParams.query = this.searchQuery;
        }

        // Add filters
        if (this.filterType) {
          requestParams.variant_type = this.filterType;
        }
        if (this.filterClassification) {
          requestParams.classification = this.filterClassification;
        }
        if (this.filterConsequence) {
          requestParams.consequence = this.filterConsequence;
        }

        const response = await getVariants(requestParams);

        window.logService.info('Variants fetched successfully', {
          count: response.data?.length || 0,
          total: response.meta?.total || 0,
          page,
          hasFilters: this.hasActiveFilters,
        });

        // Unpack the response
        let variants = response.data;

        // Apply client-side priority sorting if active
        if (this.variantTypeSortPriority) {
          window.logService.debug('Applying variant type priority sort', {
            priorityType: this.variantTypeSortPriority,
            variantsBeforeSort: variants.length,
          });
          variants = this.sortByVariantTypePriority(variants, this.variantTypeSortPriority);
        } else if (this.classificationSortPriority) {
          window.logService.debug('Applying classification priority sort', {
            priorityClassification: this.classificationSortPriority,
            variantsBeforeSort: variants.length,
          });
          variants = this.sortByClassificationPriority(variants, this.classificationSortPriority);
        }

        // Handle client-side pagination when priority sorting is active
        if (this.variantTypeSortPriority || this.classificationSortPriority) {
          this.totalItems = variants.length;
          this.totalPages = Math.ceil(variants.length / itemsPerPage);

          // Apply pagination client-side
          const start = (page - 1) * itemsPerPage;
          const end = start + itemsPerPage;
          this.variants = variants.slice(start, end);
          this.filteredCount = variants.length;
        } else {
          this.variants = variants;
          this.totalItems = response.meta.total || 0;
          this.totalPages = response.meta.total_pages || 0;
          this.filteredCount = response.meta.total || 0;
        }
      } catch (error) {
        window.logService.error('Failed to fetch variants', {
          error: error.message,
          status: error.response?.status,
          requestParams: {
            page: this.options.page,
            itemsPerPage: this.options.itemsPerPage,
            hasFilters: this.hasActiveFilters,
          },
        });
        // Show error message to user
        if (error.response?.status === 429) {
          // Rate limit error
          window.logService.warn('Rate limit exceeded on variants endpoint', {
            endpoint: '/phenopackets/aggregate/all-variants',
          });
        }
      } finally {
        this.loading = false;
      }
    },

    searchVariants() {
      // Reset to page 1 when searching
      this.options.page = 1;
      this.fetchVariants();
    },

    applyFilters() {
      window.logService.debug('Filters applied', {
        activeFilters: {
          searchQuery: this.searchQuery,
          filterType: this.filterType,
          filterClassification: this.filterClassification,
          filterConsequence: this.filterConsequence,
        },
        resetToPageOne: true,
      });
      // Reset to page 1 when applying filters
      this.options.page = 1;
      this.fetchVariants();
    },

    clearSearch() {
      this.searchQuery = '';
      this.searchVariants();
    },

    clearTypeFilter() {
      this.filterType = null;
      this.applyFilters();
    },

    clearClassificationFilter() {
      this.filterClassification = null;
      this.applyFilters();
    },

    clearConsequenceFilter() {
      this.filterConsequence = null;
      this.applyFilters();
    },

    clearAllFilters() {
      this.searchQuery = '';
      this.filterType = null;
      this.filterClassification = null;
      this.filterConsequence = null;
      this.applyFilters();
    },

    getClassificationColor(classification) {
      const upperClass = classification ? classification.toUpperCase() : '';
      if (upperClass.includes('PATHOGENIC') && !upperClass.includes('LIKELY')) {
        return 'error';
      }
      if (upperClass.includes('LIKELY_PATHOGENIC') || upperClass.includes('LIKELY PATHOGENIC')) {
        return 'warning';
      }
      if (upperClass.includes('UNCERTAIN') || upperClass.includes('VUS')) {
        return 'info';
      }
      if (upperClass.includes('LIKELY_BENIGN') || upperClass.includes('LIKELY BENIGN')) {
        return 'light-green';
      }
      if (upperClass.includes('BENIGN')) {
        return 'success';
      }
      return 'grey';
    },

    // Utility functions imported from utils modules
    getVariantType,
    extractCNotation,
    extractPNotation,
    getPathogenicityColor,
    getVariantTypeColor,

    onOptionsUpdate(newOptions) {
      window.logService.debug('Table options updated', {
        oldOptions: {
          page: this.options.page,
          itemsPerPage: this.options.itemsPerPage,
          sortBy: this.options.sortBy,
        },
        newOptions: {
          page: newOptions.page,
          itemsPerPage: newOptions.itemsPerPage,
          sortBy: newOptions.sortBy,
        },
        initialized: this.loadingInitialized,
      });

      this.options = { ...newOptions };

      // Mark as initialized and trigger initial fetch
      // This ensures fetchVariants() is only called once on mount
      if (!this.loadingInitialized) {
        this.loadingInitialized = true;
        this.fetchVariants();
      }
    },

    // Disable client-side sorting
    customSort(items) {
      return items;
    },

    // Cycle through variant types on header click (sorts with selected type on top)
    cycleVariantTypeSort() {
      // Cycle to next variant type
      this.variantTypeCycleIndex = (this.variantTypeCycleIndex + 1) % this.variantTypes.length;
      const selectedType = this.variantTypes[this.variantTypeCycleIndex];

      // Apply custom sorting: selected type first, then others
      // Create custom sort parameter that backend can handle
      this.options.sortBy = [
        { key: 'variant_type_priority', order: 'asc', priority: selectedType },
      ];

      // Store the priority type for custom sorting
      this.variantTypeSortPriority = selectedType;
      this.fetchVariants();
    },

    // Cycle through classifications on header click (sorts with selected classification on top)
    cycleClassificationSort() {
      // Cycle to next classification
      this.classificationCycleIndex =
        (this.classificationCycleIndex + 1) % this.classifications.length;
      const selectedClassification = this.classifications[this.classificationCycleIndex];

      // Apply custom sorting: selected classification first, then others
      this.options.sortBy = [
        { key: 'classification_priority', order: 'asc', priority: selectedClassification },
      ];

      // Store the priority classification for custom sorting
      this.classificationSortPriority = selectedClassification;
      this.fetchVariants();
    },

    // Sort variants with priority type on top
    sortByVariantTypePriority(variants, priorityType) {
      return [...variants].sort((a, b) => {
        const aType = this.getVariantType(a);
        const bType = this.getVariantType(b);

        // Priority type comes first
        if (aType === priorityType && bType !== priorityType) return -1;
        if (aType !== priorityType && bType === priorityType) return 1;

        // Both same priority or both not priority - maintain original order
        return 0;
      });
    },

    // Sort variants with priority classification on top
    sortByClassificationPriority(variants, priorityClassification) {
      return [...variants].sort((a, b) => {
        const aClass = a.classificationVerdict;
        const bClass = b.classificationVerdict;

        // Priority classification comes first
        if (aClass === priorityClassification && bClass !== priorityClassification) return -1;
        if (aClass !== priorityClassification && bClass === priorityClassification) return 1;

        // Both same priority or both not priority - maintain original order
        return 0;
      });
    },

    goToFirstPage() {
      this.options.page = 1;
    },

    goToPreviousPage() {
      if (this.options.page > 1) {
        this.options.page--;
      }
    },

    goToNextPage() {
      if (this.options.page < this.totalPages) {
        this.options.page++;
      }
    },

    goToLastPage() {
      this.options.page = this.totalPages;
    },

    handleRowClick(event, row) {
      // Navigate to variant detail page using variant_id
      if (row.item && row.item.variant_id) {
        window.logService.info('Navigating to variant detail', {
          variantId: row.item.variant_id,
          simpleId: row.item.simple_id,
        });
        this.$router.push(`/variants/${row.item.variant_id}`);
      }
    },
  },
};
</script>

<style scoped>
/* Ensure header cells are bold */
.font-weight-bold {
  font-weight: bold;
}

/* Truncate long text in table cells */
.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Make table rows look clickable */
:deep(tbody tr) {
  cursor: pointer;
}

:deep(tbody tr:hover) {
  background-color: rgba(0, 0, 0, 0.04);
}
</style>
