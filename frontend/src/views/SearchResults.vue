<template>
  <v-container fluid>
    <v-row>
      <!-- Sidebar with Faceted Filters -->
      <v-col cols="12" md="3">
        <FacetedFilters
          v-model="selectedFacets"
          :facets="facets"
          @filter-change="handleFilterChange"
        />
      </v-col>

      <!-- Main Content Area -->
      <v-col cols="12" md="9">
        <!-- Header with Title and Actions -->
        <v-row>
          <v-col cols="12">
            <div class="d-flex justify-space-between align-center mb-4">
              <div>
                <h2>
                  Search Results
                  <v-chip v-if="!loading" size="small" class="ml-2">
                    {{ totalResults }} results
                  </v-chip>
                </h2>
                <v-chip-group v-if="Object.keys(filters).length > 0" class="mt-2">
                  <v-chip v-if="filters.q" closeable @click:close="removeFilter('q')">
                    Text: {{ filters.q }}
                  </v-chip>
                  <v-chip v-if="filters.hpo_id" closeable @click:close="removeFilter('hpo_id')">
                    HPO: {{ filters.hpo_id }}
                  </v-chip>
                  <v-chip v-if="filters.gene" closeable @click:close="removeFilter('gene')">
                    Gene: {{ filters.gene }}
                  </v-chip>
                  <v-chip v-if="filters.sex" closeable @click:close="removeFilter('sex')">
                    Sex: {{ filters.sex }}
                  </v-chip>
                  <v-chip v-if="filters.pmid" closeable @click:close="removeFilter('pmid')">
                    PMID: {{ filters.pmid }}
                  </v-chip>
                </v-chip-group>
                <p v-else class="text-grey mt-2">No text filters applied.</p>
              </div>

              <!-- Sort and Export Actions -->
              <div class="d-flex gap-2">
                <v-select
                  v-model="sortBy"
                  :items="sortOptions"
                  label="Sort by"
                  density="compact"
                  style="max-width: 200px"
                  hide-details
                  @update:model-value="handleSortChange"
                />
                <v-menu>
                  <template #activator="{ props }">
                    <v-btn
                      v-bind="props"
                      color="primary"
                      variant="outlined"
                      prepend-icon="mdi-download"
                      :disabled="results.length === 0"
                    >
                      Export
                    </v-btn>
                  </template>
                  <v-list>
                    <v-list-item @click="exportResults('csv')">
                      <v-list-item-title>Export as CSV</v-list-item-title>
                    </v-list-item>
                    <v-list-item @click="exportResults('json')">
                      <v-list-item-title>Export as JSON</v-list-item-title>
                    </v-list-item>
                  </v-list>
                </v-menu>
              </div>
            </div>
          </v-col>
        </v-row>

        <!-- Loading State -->
        <v-row v-if="loading">
          <v-col cols="12" class="text-center">
            <v-progress-circular indeterminate color="primary" size="64" />
            <p class="mt-4 text-h6">Searching phenopackets...</p>
          </v-col>
        </v-row>

        <!-- Results Table -->
        <v-row v-else>
          <v-col cols="12">
            <v-data-table
              :headers="headers"
              :items="results"
              :items-length="totalResults"
              class="elevation-1"
              hide-default-footer
              @click:row="navigateToPhenopacket"
            >
              <template #item.search_rank="{ item }">
                <v-chip v-if="item.search_rank" color="green" size="small">
                  {{ (item.search_rank * 100).toFixed(1) }}% match
                </v-chip>
                <span v-else>-</span>
              </template>
              <template #item.subject.id="{ item }">
                <router-link :to="`/phenopackets/${item.id}`">{{ item.subject.id }}</router-link>
              </template>
              <template #no-data>
                <v-alert type="info" variant="tonal" class="ma-4">
                  No phenopackets match your search criteria. Try adjusting your filters.
                </v-alert>
              </template>
            </v-data-table>

            <!-- Pagination Controls -->
            <div v-if="totalResults > 0" class="d-flex justify-space-between align-center mt-4">
              <div class="d-flex align-center gap-2">
                <v-select
                  v-model="pageSize"
                  :items="pageSizeOptions"
                  density="compact"
                  variant="outlined"
                  hide-details
                  style="max-width: 150px"
                  @update:model-value="handlePageSizeChange"
                />
                <span class="text-caption text-grey">
                  Showing {{ (currentPage - 1) * pageSize + 1 }}-{{
                    Math.min(currentPage * pageSize, totalResults)
                  }}
                  of {{ totalResults }}
                </span>
              </div>

              <v-pagination
                v-model="currentPage"
                :length="totalPages"
                :total-visible="7"
                @update:model-value="handlePageChange"
              />
            </div>
          </v-col>
        </v-row>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { searchPhenopackets, getSearchFacets } from '@/api';
import FacetedFilters from '@/components/FacetedFilters.vue';

const route = useRoute();
const router = useRouter();

const filters = computed(() => {
  const { page, pageSize: size, sex, genes, phenotypes, ...textFilters } = route.query;
  return textFilters;
});
const results = ref([]);
const loading = ref(false);
const totalResults = ref(0);
const sortBy = ref(route.query.sort || 'relevance');
const currentPage = ref(parseInt(route.query.page) || 1);
const pageSize = ref(parseInt(route.query.pageSize) || 20);
const selectedFacets = ref({
  sex: route.query.sex ? (Array.isArray(route.query.sex) ? route.query.sex : [route.query.sex]) : [],
  pathogenicity: route.query.pathogenicity ? (Array.isArray(route.query.pathogenicity) ? route.query.pathogenicity : [route.query.pathogenicity]) : [],
  genes: route.query.genes ? (Array.isArray(route.query.genes) ? route.query.genes : [route.query.genes]) : [],
  phenotypes: route.query.phenotypes ? (Array.isArray(route.query.phenotypes) ? route.query.phenotypes : [route.query.phenotypes]) : [],
});

const facets = ref({
  sex: [],
  pathogenicity: [],
  genes: [],
  phenotypes: [],
});

const sortOptions = [
  { title: 'Relevance', value: 'relevance' },
  { title: 'Subject ID (A-Z)', value: 'subject_id_asc' },
  { title: 'Subject ID (Z-A)', value: 'subject_id_desc' },
  { title: 'Sex', value: 'sex' },
  { title: 'Date Added (Newest)', value: 'created_desc' },
  { title: 'Date Added (Oldest)', value: 'created_asc' },
];

const headers = [
  { title: 'ID', value: 'subject.id', sortable: false },
  { title: 'Sex', value: 'subject.sex', sortable: false },
  { title: 'Relevance', value: 'search_rank', sortable: false },
];

const totalPages = computed(() => Math.ceil(totalResults.value / pageSize.value));

const pageSizeOptions = [
  { title: '10 per page', value: 10 },
  { title: '20 per page', value: 20 },
  { title: '50 per page', value: 50 },
  { title: '100 per page', value: 100 },
];

// Update URL with all search state
const updateURL = () => {
  const query = {
    ...filters.value, // Keep text filters (q, hpo_id, gene, sex, pmid)
  };

  // Add sort if not default
  if (sortBy.value !== 'relevance') {
    query.sort = sortBy.value;
  }

  // Add pagination if not default
  if (currentPage.value !== 1) {
    query.page = currentPage.value;
  }
  if (pageSize.value !== 20) {
    query.pageSize = pageSize.value;
  }

  // Add facet filters if selected
  if (selectedFacets.value.sex.length > 0) {
    query.sex = selectedFacets.value.sex;
  }
  if (selectedFacets.value.pathogenicity.length > 0) {
    query.pathogenicity = selectedFacets.value.pathogenicity;
  }
  if (selectedFacets.value.genes.length > 0) {
    query.genes = selectedFacets.value.genes;
  }
  if (selectedFacets.value.phenotypes.length > 0) {
    query.phenotypes = selectedFacets.value.phenotypes;
  }

  router.replace({ query });
};

const fetchResults = async () => {
  loading.value = true;
  try {
    // Build search params from route query and selected facets
    const searchParams = {
      ...filters.value,
      rank_by_relevance: sortBy.value === 'relevance',
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
    };

    // Add facet filters to search params
    if (selectedFacets.value.sex.length > 0) {
      searchParams.sex = selectedFacets.value.sex[0]; // API accepts single sex value
    }
    if (selectedFacets.value.genes.length > 0) {
      searchParams.gene = selectedFacets.value.genes[0]; // API accepts single gene
    }
    if (selectedFacets.value.phenotypes.length > 0) {
      searchParams.hpo_id = selectedFacets.value.phenotypes[0]; // API accepts single HPO
    }

    const { data } = await searchPhenopackets(searchParams);
    results.value = data.data.map((pp) => ({
      ...pp.attributes,
      id: pp.id,
      search_rank: pp.meta?.search_rank,
    }));
    totalResults.value = data.meta.total;

    // Log successful search
    if (window.logService) {
      window.logService.info('Search completed', {
        query: searchParams.q,
        results: totalResults.value,
        page: currentPage.value,
        pageSize: pageSize.value,
      });
    }
  } catch (error) {
    if (window.logService) {
      window.logService.error('Search failed', { error: error.message });
    } else {
      console.error('Search failed', { error: error.message });
    }
    results.value = [];
    totalResults.value = 0;
  } finally {
    loading.value = false;
  }
};

const fetchFacets = async () => {
  try {
    const { data } = await getSearchFacets(filters.value);
    facets.value = data.facets;

    if (window.logService) {
      window.logService.debug('Facets loaded', {
        sex: facets.value.sex.length,
        genes: facets.value.genes.length,
        phenotypes: facets.value.phenotypes.length,
      });
    }
  } catch (error) {
    if (window.logService) {
      window.logService.error('Failed to load facets', { error: error.message });
    } else {
      console.error('Failed to load facets', { error: error.message });
    }
  }
};

const removeFilter = (key) => {
  const newQuery = { ...route.query };
  delete newQuery[key];
  router.push({ query: newQuery });
};

const handleFilterChange = (newFilters) => {
  selectedFacets.value = newFilters;
  currentPage.value = 1; // Reset to first page when filters change
  updateURL();
  if (window.logService) {
    window.logService.info('Facet filters changed', {
      sex: newFilters.sex,
      pathogenicity: newFilters.pathogenicity,
      genes: newFilters.genes,
      phenotypes: newFilters.phenotypes,
    });
  }
};

const handleSortChange = () => {
  currentPage.value = 1; // Reset to first page when sort changes
  updateURL();
  if (window.logService) {
    window.logService.info('Sort order changed', { sortBy: sortBy.value });
  }
};

const handlePageChange = (page) => {
  currentPage.value = page;
  updateURL();
  if (window.logService) {
    window.logService.info('Page changed', { page: currentPage.value });
  }
};

const handlePageSizeChange = () => {
  currentPage.value = 1; // Reset to first page when page size changes
  updateURL();
  if (window.logService) {
    window.logService.info('Page size changed', { pageSize: pageSize.value });
  }
};

const navigateToPhenopacket = (event, { item }) => {
  if (item && item.id) {
    router.push(`/phenopackets/${item.id}`);
  }
};

const exportResults = (format) => {
  if (results.value.length === 0) {
    return;
  }

  try {
    if (format === 'csv') {
      exportAsCSV();
    } else if (format === 'json') {
      exportAsJSON();
    }

    if (window.logService) {
      window.logService.info('Exported search results', {
        format,
        count: results.value.length,
      });
    }
  } catch (error) {
    if (window.logService) {
      window.logService.error('Export failed', { error: error.message, format });
    } else {
      console.error('Export failed', { error: error.message, format });
    }
  }
};

const exportAsCSV = () => {
  // Extract key fields for CSV export
  const csvData = results.value.map((item) => ({
    'Phenopacket ID': item.id,
    'Subject ID': item.subject?.id || '-',
    Sex: item.subject?.sex || '-',
    'Primary Disease':
      item.diseases?.[0]?.term?.label ||
      item.interpretations?.[0]?.diagnosis?.disease?.label ||
      '-',
    'Phenotype Count': item.phenotypicFeatures?.length || 0,
    'Has Variants': item.interpretations?.length > 0 ? 'Yes' : 'No',
    'Relevance Score': item.search_rank ? `${(item.search_rank * 100).toFixed(1)}%` : '-',
  }));

  // Convert to CSV string
  const headers = Object.keys(csvData[0]);
  const csvContent = [
    headers.join(','),
    ...csvData.map((row) =>
      headers.map((header) => `"${String(row[header]).replace(/"/g, '""')}"`).join(',')
    ),
  ].join('\n');

  // Download
  downloadFile(csvContent, `phenopackets-search-results-${Date.now()}.csv`, 'text/csv');
};

const exportAsJSON = () => {
  // Export full phenopacket data
  const jsonContent = JSON.stringify(
    {
      metadata: {
        exportDate: new Date().toISOString(),
        totalResults: totalResults.value,
        exportedResults: results.value.length,
        searchCriteria: filters.value,
      },
      phenopackets: results.value,
    },
    null,
    2
  );

  downloadFile(jsonContent, `phenopackets-search-results-${Date.now()}.json`, 'application/json');
};

const downloadFile = (content, filename, mimeType) => {
  const blob = new Blob([content], { type: mimeType });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
};

// Fetch results and facets on component mount
onMounted(() => {
  fetchResults();
  fetchFacets();
});

// Watch for changes in query parameters and sync to state
watch(
  () => route.query,
  (newQuery) => {
    // Sync sort
    sortBy.value = newQuery.sort || 'relevance';

    // Sync pagination
    currentPage.value = parseInt(newQuery.page) || 1;
    pageSize.value = parseInt(newQuery.pageSize) || 20;

    // Sync facet filters
    selectedFacets.value = {
      sex: newQuery.sex ? (Array.isArray(newQuery.sex) ? newQuery.sex : [newQuery.sex]) : [],
      pathogenicity: newQuery.pathogenicity ? (Array.isArray(newQuery.pathogenicity) ? newQuery.pathogenicity : [newQuery.pathogenicity]) : [],
      genes: newQuery.genes ? (Array.isArray(newQuery.genes) ? newQuery.genes : [newQuery.genes]) : [],
      phenotypes: newQuery.phenotypes ? (Array.isArray(newQuery.phenotypes) ? newQuery.phenotypes : [newQuery.phenotypes]) : [],
    };

    // Fetch with new parameters
    fetchResults();
    fetchFacets();
  },
  { deep: true }
);
</script>

<style scoped>
.v-data-table :deep(tbody tr) {
  cursor: pointer;
}

.gap-2 {
  gap: 8px;
}
</style>
