<template>
  <v-card variant="flat" class="pa-8 mx-auto search-card" theme="light">
    <v-autocomplete
      v-model="selectedItem"
      v-model:search="searchQuery"
      :items="suggestions"
      :loading="loading"
      placeholder="Search by HPO term, gene, or keyword..."
      append-inner-icon="mdi-magnify"
      density="comfortable"
      variant="solo"
      auto-select-first
      clearable
      rounded
      full-width
      return-object
      item-title="label"
      item-value="hpo_id"
      @update:search="debouncedSearch"
      @update:model-value="onSelect"
      @keyup.enter="onEnter"
    >
      <template #item="{ props, item }">
        <v-list-item v-bind="props" :title="item.raw.label">
          <v-list-item-subtitle>
            {{ item.raw.hpo_id }} · {{ item.raw.phenopacket_count }} phenopackets
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
import { getHPOAutocomplete } from '@/api';
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
    const response = await getHPOAutocomplete(query);
    suggestions.value = response.data.data || [];
  } catch (error) {
    suggestions.value = [];
    if (window.logService) {
      window.logService.error('HPO autocomplete failed', { error: error.message });
    } else {
      console.error('HPO autocomplete failed', { error: error.message });
    }
  } finally {
    loading.value = false;
  }
};

const debouncedSearch = debounce(fetchSuggestions, 300);

const onSelect = (item) => {
  if (!item) return;

  addRecentSearch(item.label);
  // When selecting from HPO autocomplete, only use hpo_id for precise results
  router.push({
    name: 'SearchResults',
    query: { hpo_id: item.hpo_id },
  });
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
/* Typical width is 600px on larger devices, with a minimum of 400px for smaller screens */
.search-card {
  min-width: 350px;
  width: 600px;
}

@media (max-width: 600px) {
  .search-card {
    width: 100%;
  }
}

.mx-auto {
  margin: 0 auto;
}
</style>
