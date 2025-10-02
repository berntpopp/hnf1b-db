<!-- src/views/SearchResults.vue -->
<template>
  <v-container>
    <v-row>
      <v-col cols="12">
        <h2>Search Results for "{{ searchQuery }}"</h2>
      </v-col>
    </v-row>

    <!-- Show a loading indicator -->
    <v-row v-if="loading">
      <v-col cols="12">
        <v-progress-circular
          color="primary"
          indeterminate
        />
        <span>Loading...</span>
      </v-col>
    </v-row>

    <!-- If no results found, display a message -->
    <v-row v-else-if="allResultsEmpty">
      <v-col cols="12">
        <p>No results found for "{{ searchQuery }}"</p>
      </v-col>
    </v-row>

    <!-- Otherwise, display the flattened results table -->
    <v-row v-else>
      <v-col cols="12">
        <v-data-table
          :headers="tableHeaders"
          :items="flattenedResults"
          :items-per-page="10"
          class="elevation-1"
        >
          <!-- Custom rendering for the ID column based on category -->
          <template #item.id="{ item }">
            <template v-if="item.category === 'Individuals'">
              <v-chip
                color="lime lighten-2"
                class="ma-2"
                small
                link
                :to="`/individuals/${item.id}`"
              >
                {{ item.id }}
                <v-icon right>
                  mdi-account
                </v-icon>
              </v-chip>
            </template>
            <template v-else-if="item.category === 'Variants'">
              <v-chip
                color="pink lighten-4"
                class="ma-2"
                small
                link
                :to="`/variants/${item.id}`"
              >
                {{ item.id }}
                <v-icon right>
                  mdi-dna
                </v-icon>
              </v-chip>
            </template>
            <template v-else-if="item.category === 'Publications'">
              <v-chip
                color="cyan accent-2"
                class="ma-2"
                small
                link
                :to="`/publications/${item.id}`"
              >
                pub{{ item.id }}
                <v-icon right>
                  mdi-book-open-blank-variant
                </v-icon>
              </v-chip>
            </template>
            <template v-else>
              {{ item.id }}
            </template>
          </template>

          <!-- Render the Category and Matched Fields normally -->
          <template #item.category="{ item }">
            <span>{{ item.category }}</span>
          </template>
          <template #item.matchedDisplay="{ item }">
            <span>{{ item.matchedDisplay }}</span>
          </template>
        </v-data-table>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
import { ref, onMounted, computed } from 'vue';
import { useRoute } from 'vue-router';
import { search } from '@/api/index.js';

/**
 * Formats the "matched" object into a display string.
 *
 * @param {Object} matched - e.g. { hg38: "chr17-..." }
 * @returns {string} The formatted string.
 */
function formatMatched(matched) {
  if (!matched) return '';
  return Object.entries(matched)
    .map(([key, val]) => `${key}: ${val}`)
    .join('; ');
}

export default {
  name: 'SearchResults',
  setup() {
    const route = useRoute();
    // Use consistent query parameter "q"
    const searchQuery = ref(route.query.q || '');
    const loading = ref(false);

    // Expected shape from the /api/search endpoint.
    const results = ref({
      individuals: { data: [] },
      variants: { data: [] },
      publications: { data: [] },
    });

    // Compute arrays for each category with additional fields.
    const individualsData = computed(() =>
      results.value.individuals.data.map((item) => ({
        ...item,
        matchedDisplay: formatMatched(item.matched),
        category: 'Individuals',
      }))
    );
    const variantsData = computed(() =>
      results.value.variants.data.map((item) => ({
        ...item,
        matchedDisplay: formatMatched(item.matched),
        category: 'Variants',
      }))
    );
    const publicationsData = computed(() =>
      results.value.publications.data.map((item) => ({
        ...item,
        matchedDisplay: formatMatched(item.matched),
        category: 'Publications',
      }))
    );

    // Flatten all results into one array.
    const flattenedResults = computed(() => [
      ...individualsData.value,
      ...variantsData.value,
      ...publicationsData.value,
    ]);

    // Check if no results were found.
    const allResultsEmpty = computed(() => flattenedResults.value.length === 0);

    // Define table headers for the flattened table.
    const tableHeaders = [
      { title: 'Category', value: 'category' },
      { title: 'ID', value: 'id' },
      { title: 'Matched Fields', value: 'matchedDisplay' },
    ];

    /**
     * Fetch search results using the query from the URL.
     */
    async function doSearch() {
      const query = searchQuery.value.trim();
      if (!query) return;
      loading.value = true;
      try {
        // reduceDoc = true returns only minimal fields.
        const { data: searchData } = await search(query, null, true);
        if (searchData && searchData.results) {
          results.value = searchData.results;
        }
      } catch (err) {
        console.error('Search error:', err);
      } finally {
        loading.value = false;
      }
    }

    // Trigger search when the component mounts.
    onMounted(() => {
      doSearch();
    });

    return {
      searchQuery,
      loading,
      flattenedResults,
      allResultsEmpty,
      tableHeaders,
      doSearch,
    };
  },
};
</script>

<style scoped>
/* Optional: add additional styling for table spacing, cursor pointers, etc. */
</style>
