<!-- src/components/SearchCard.vue -->
<template>
  <v-card
    variant="flat"
    class="pa-8 mx-auto search-card"
    theme="light"
  >
    <v-autocomplete
      v-model="selectedItem"
      v-model:search="typedText"
      :items="limitedSuggestions"
      :item-title="getItemTitle"
      item-value="id"
      placeholder="Start typing to search publications, variants and individuals..."
      append-inner-icon="mdi-magnify"
      density="comfortable"
      variant="solo"
      auto-select-first
      rounded
      full-width
      :loading="loading"
      :filter="filterFn"
      return-object
      :menu-props="{ maxWidth: '100%' }"
      @click:append-inner="searchAndNavigate"
      @change="onAutocompleteChange"
      @keyup.enter="onEnterPressed"
    />
  </v-card>
</template>

<script>
import { ref, watch, computed } from 'vue';
import { useRouter } from 'vue-router';
import { search } from '@/api/index.js';

/**
 * Debounce function to limit how often a function is called.
 *
 * @param {Function} func The function to debounce.
 * @param {number} wait The delay in milliseconds.
 * @returns {Function} The debounced function.
 */
function debounce(func, wait) {
  let timeout;
  return function debounced(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}

export default {
  name: 'SearchCard',
  setup() {
    const router = useRouter();
    const selectedItem = ref(null);
    const typedText = ref('');
    const loading = ref(false);
    const searchSuggestions = ref([]);

    // Limit suggestions to the first 10 results.
    const limitedSuggestions = computed(() => searchSuggestions.value.slice(0, 10));

    /**
     * Formats the matched object into a semicolon-separated string.
     *
     * @param {Object} matched The matched object.
     * @returns {string} A formatted string.
     */
    function formatMatched(matched) {
      if (!matched) return '';
      return Object.entries(matched)
        .map(([key, val]) => `${key}: ${val}`)
        .join('; ');
    }

    /**
     * Returns a formatted title for a suggestion item.
     *
     * @param {Object} item A suggestion item.
     * @returns {string} A formatted title.
     */
    function getItemTitle(item) {
      if (!item) return '';
      return `${item.id} [${item.collection}] - ${formatMatched(item.matched)}`;
    }

    /**
     * Flattens the API response into one array of suggestion items.
     *
     * @param {Object} apiData The API response.
     * @returns {Array} The flattened array.
     */
    function formatSearchResults(apiData) {
      if (!apiData || !apiData.results) return [];
      const { individuals, variants, publications } = apiData.results;
      return [
        ...individuals.data.map((d) => ({ ...d, collection: 'individuals' })),
        ...variants.data.map((d) => ({ ...d, collection: 'variants' })),
        ...publications.data.map((d) => ({ ...d, collection: 'publications' })),
      ];
    }

    /**
     * Navigates to the detail page by constructing the URL.
     *
     * @param {string} collection The collection name.
     * @param {string} id The unique identifier.
     */
    function navigateToDetail(collection, id) {
      if (!collection || !id) return;
      router.push(`/${collection}/${id}`);
    }

    /**
     * Handles autocomplete selection changes.
     *
     * @param {Object} item The item selected from the suggestions.
     */
    function onAutocompleteChange(item) {
      if (item && item.collection && item.id) {
        navigateToDetail(item.collection, item.id);
      }
    }

    /**
     * Called when the Enter key is pressed.
     * Navigates to the detail page if a suggestion is selected or,
     * if only one suggestion is available, or otherwise to the search results page.
     */
    function onEnterPressed() {
      if (selectedItem.value && selectedItem.value.collection && selectedItem.value.id) {
        navigateToDetail(selectedItem.value.collection, selectedItem.value.id);
      } else if (searchSuggestions.value.length === 1) {
        const onlyResult = searchSuggestions.value[0];
        navigateToDetail(onlyResult.collection, onlyResult.id);
      } else {
        searchAndNavigate();
      }
    }

    /**
     * Navigates to the search results page using the current query.
     */
    function searchAndNavigate() {
      const query = typedText.value.trim();
      if (!query) return;
      router.push({ name: 'SearchResults', query: { q: query } });
    }

    /**
     * A no-op filter function.
     *
     * @returns {boolean} Always returns true.
     */
    function filterFn() {
      return true;
    }

    // Debounced search function to limit API calls.
    const debouncedSearch = debounce(async (newVal) => {
      if (!newVal) {
        searchSuggestions.value = [];
        return;
      }
      loading.value = true;
      try {
        const { data: searchData } = await search(newVal, null, true);
        searchSuggestions.value = formatSearchResults(searchData);
      } catch (err) {
        console.error('Search error:', err);
      } finally {
        loading.value = false;
      }
    }, 300);

    watch(typedText, (newVal) => {
      debouncedSearch(newVal);
    });

    return {
      selectedItem,
      typedText,
      loading,
      searchSuggestions,
      limitedSuggestions,
      onAutocompleteChange,
      onEnterPressed,
      searchAndNavigate,
      getItemTitle,
      filterFn,
    };
  },
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
