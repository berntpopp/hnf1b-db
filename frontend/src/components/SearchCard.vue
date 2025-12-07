<template>
  <v-card variant="flat" class="pa-8 mx-auto search-card" theme="light">
    <v-autocomplete
      v-model="selectedItem"
      v-model:search="searchQuery"
      :items="suggestions"
      :loading="loading"
      placeholder="Search variants, phenotypes, publications..."
      append-inner-icon="mdi-magnify"
      density="comfortable"
      variant="solo"
      auto-select-first
      clearable
      rounded
      full-width
      return-object
      item-title="label"
      item-value="id"
      @update:search="debouncedSearch"
      @update:model-value="onSelect"
      @keyup.enter="onEnter"
    >
      <template #item="{ props, item }">
        <v-list-item v-bind="props" :title="item.raw.label">
          <template #prepend>
            <v-icon v-if="item.raw.type === 'Gene'" color="primary">mdi-dna</v-icon>
            <v-icon v-else-if="item.raw.type === 'Gene Feature'" color="purple">
              mdi-creation
            </v-icon>
            <v-icon v-else-if="item.raw.type === 'Variant'" color="error">mdi-flash</v-icon>
            <v-icon v-else-if="item.raw.type === 'Phenopacket'" color="teal">mdi-account</v-icon>
            <v-icon v-else-if="item.raw.type === 'Publication'" color="orange">
              mdi-book-open-page-variant
            </v-icon>
            <v-icon v-else color="grey">mdi-magnify</v-icon>
          </template>
          <v-list-item-subtitle>
            {{ item.raw.type }}
            <span v-if="item.raw.subtype"> · {{ item.raw.subtype }}</span>
            <span v-if="item.raw.extra_info"> · {{ item.raw.extra_info }}</span>
          </v-list-item-subtitle>
        </v-list-item>
      </template>

      <template v-if="recentSearches.length > 0" #prepend-item>
        <div class="d-flex justify-space-between align-center px-4 py-2">
          <v-list-subheader class="px-0">Recent Searches</v-list-subheader>
          <v-btn
            variant="text"
            size="x-small"
            color="error"
            @click.stop="handleClearRecentSearches"
          >
            Clear all
          </v-btn>
        </div>
        <v-list-item
          v-for="recent in recentSearches"
          :key="recent"
          @click="searchFromRecent(recent)"
        >
          <v-list-item-title>{{ recent }}</v-list-item-title>
          <template #prepend>
            <v-icon>mdi-history</v-icon>
          </template>
        </v-list-item>
        <v-divider />
      </template>
    </v-autocomplete>
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { searchAutocomplete } from '@/api';
import { addRecentSearch, getRecentSearches, clearRecentSearches } from '@/utils/searchHistory';
import { debounce } from '@/utils/debounce';

const router = useRouter();
const searchQuery = ref('');
const selectedItem = ref(null);
const suggestions = ref([]);
const loading = ref(false);
const recentSearches = ref([]);

// Load recent searches on mount
onMounted(() => {
  recentSearches.value = getRecentSearches();
});

const fetchSuggestions = async (query) => {
  if (!query || query.length < 2) {
    suggestions.value = [];
    return;
  }

  loading.value = true;
  try {
    const response = await searchAutocomplete(query);
    suggestions.value = response.data.results || [];
  } catch (error) {
    suggestions.value = [];
    if (window.logService) {
      window.logService.error('Autocomplete failed', { error: error.message });
    } else {
      console.error('Autocomplete failed', { error: error.message });
    }
  } finally {
    loading.value = false;
  }
};

const debouncedSearch = debounce(fetchSuggestions, 300);

const onSelect = (item) => {
  if (!item) return;

  addRecentSearch(item.label);

  // Handle different result types
  if (item.type === 'Phenopacket') {
    router.push(`/phenopackets/${item.id}`);
  } else if (item.type === 'Publication') {
    // Navigate to publications list filtered by this publication
    // Or a detail page if it existed
    router.push({
      name: 'Publications',
      query: { q: item.id }, // Search by PMID
    });
  } else if (item.type === 'Variant') {
    // Navigate to variants list filtered by this variant
    // Assuming item.id is usable as a query (e.g. HGVS or ID)
    router.push({
      name: 'Variants',
      query: { query: item.label }, // Search by label (usually HGVS)
    });
  } else {
    // Default fallback: Global Search Results
    router.push({
      name: 'SearchResults',
      query: { q: item.label },
    });
  }
};

const onEnter = () => {
  if (selectedItem.value) {
    onSelect(selectedItem.value);
  } else if (searchQuery.value) {
    addRecentSearch(searchQuery.value);
    router.push({
      name: 'SearchResults',
      query: { q: searchQuery.value },
    });
  }
};

const searchFromRecent = (recentTerm) => {
  searchQuery.value = recentTerm;
  addRecentSearch(recentTerm);
  router.push({
    name: 'SearchResults',
    query: { q: recentTerm },
  });
};

const handleClearRecentSearches = () => {
  clearRecentSearches();
  recentSearches.value = [];
  if (window.logService) {
    window.logService.info('User cleared recent searches from SearchCard');
  }
};
</script>

<style scoped>
.search-card {
  width: 100%;
  max-width: 800px;
  background-color: transparent !important; /* Allow parent background to likely show through or be set by parent */
}

.mx-auto {
  margin: 0 auto;
}
</style>
