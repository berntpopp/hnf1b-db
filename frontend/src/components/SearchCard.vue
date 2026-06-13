<template>
  <v-card variant="flat" class="pa-8 mx-auto search-card" theme="light">
    <v-autocomplete
      v-model="selectedItem"
      v-model:search="searchQuery"
      :items="suggestions"
      :loading="loading"
      label="Search the database"
      placeholder="Search variants, phenotypes, publications..."
      append-inner-icon="mdi-magnify"
      density="comfortable"
      variant="solo"
      auto-select-first
      clearable
      rounded
      full-width
      return-object
      no-filter
      item-title="label"
      item-value="id"
      :menu-props="{ maxHeight: 420 }"
      aria-label="Search variants, phenotypes, and publications"
      @update:search="debouncedSearch"
      @update:model-value="onSelect"
      @keyup.enter="onEnter"
    >
      <template #item="{ props, item }">
        <v-list-item v-bind="props" :title="null">
          <template #prepend>
            <v-icon :color="iconFor(rawOf(item).type).color">
              {{ iconFor(rawOf(item).type).icon }}
            </v-icon>
          </template>
          <template #title>
            <span class="search-item-title">
              <template v-for="(segment, i) in highlightSegments(rawOf(item).label)" :key="i">
                <span v-if="segment.match" class="search-hl">{{ segment.text }}</span>
                <template v-else>{{ segment.text }}</template>
              </template>
            </span>
          </template>
          <template #subtitle>
            {{ rawOf(item).type }}
            <span v-if="rawOf(item).subtype"> · {{ rawOf(item).subtype }}</span>
            <span v-if="rawOf(item).extra_info"> · {{ rawOf(item).extra_info }}</span>
          </template>
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

      <!--
        Helpful empty state. With `no-filter` the dropdown trusts the
        server's (fuzzy/substring) results, so when it is empty we tell the
        user why and offer to escalate to the full search-results page rather
        than showing a bare "No data available".
      -->
      <template #no-data>
        <div
          v-if="noDataState !== 'recent'"
          class="px-4 py-3 text-medium-emphasis search-no-data"
          role="status"
          aria-live="polite"
        >
          <template v-if="noDataState === 'loading'">
            <v-progress-circular indeterminate size="16" width="2" class="mr-2" />
            Searching…
          </template>
          <template v-else-if="noDataState === 'empty'">
            Start typing to search variants, phenotypes, and publications.
          </template>
          <template v-else-if="noDataState === 'tooShort'">
            Type at least 2 characters to see suggestions.
          </template>
          <template v-else>
            <div class="mb-2">No quick matches for “{{ trimmedQuery }}”.</div>
            <v-btn
              size="small"
              variant="tonal"
              color="primary"
              prepend-icon="mdi-magnify"
              @mousedown.prevent
              @click="searchEverything"
            >
              Search everything for “{{ trimmedQuery }}”
            </v-btn>
          </template>
        </div>
      </template>
    </v-autocomplete>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
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

const trimmedQuery = computed(() => (searchQuery.value ?? '').trim());

/**
 * Drives the #no-data slot so the dropdown explains itself instead of
 * rendering Vuetify's default "No data available".
 * @returns {'loading'|'recent'|'empty'|'tooShort'|'noMatch'}
 */
const noDataState = computed(() => {
  if (loading.value) return 'loading';
  const q = trimmedQuery.value;
  if (q.length === 0) return recentSearches.value.length > 0 ? 'recent' : 'empty';
  if (q.length < 2) return 'tooShort';
  return 'noMatch';
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

/** Map a result type to its suggestion icon + colour. */
const TYPE_ICONS = {
  Gene: { icon: 'mdi-dna', color: 'primary' },
  'Gene Feature': { icon: 'mdi-creation', color: 'purple' },
  Variant: { icon: 'mdi-flash', color: 'error' },
  Phenopacket: { icon: 'mdi-account', color: 'teal' },
  Publication: { icon: 'mdi-book-open-page-variant', color: 'orange' },
};
const iconFor = (type) => TYPE_ICONS[type] ?? { icon: 'mdi-magnify', color: 'grey' };

/**
 * Resolve the underlying suggestion object from an autocomplete item slot.
 * Vuetify hands the raw suggestion object directly here, but tolerate the
 * ``InternalItem`` ``{ raw }`` shape too so the template is robust to either.
 * @param {object} item
 * @returns {{ label?: string, type?: string, subtype?: string, extra_info?: string }}
 */
const rawOf = (item) => item?.raw ?? item ?? {};

/**
 * Split a label around the first case-insensitive occurrence of the current
 * query so it can be rendered with the matched run emphasized. Returns the
 * whole label as a single non-matching segment when the literal query is not
 * present (e.g. fuzzy/typo matches), so it is always safe to render.
 * @param {string} label
 * @returns {Array<{ text: string, match: boolean }>}
 */
const highlightSegments = (label) => {
  const text = label ?? '';
  const q = trimmedQuery.value;
  if (!q) return [{ text, match: false }];
  const idx = text.toLowerCase().indexOf(q.toLowerCase());
  if (idx === -1) return [{ text, match: false }];
  return [
    { text: text.slice(0, idx), match: false },
    { text: text.slice(idx, idx + q.length), match: true },
    { text: text.slice(idx + q.length), match: false },
  ].filter((segment) => segment.text.length > 0);
};

/** Navigate to the full search-results page for a free-text term. */
const goToFullSearch = (term) => {
  const q = (term ?? '').trim();
  if (!q) return;
  addRecentSearch(q);
  router.push({
    name: 'SearchResults',
    query: { q },
  });
};

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
      query: { q: item.label }, // Search by label (usually HGVS)
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
  } else {
    goToFullSearch(searchQuery.value);
  }
};

/** "Search everything" affordance shown in the empty-state slot. */
const searchEverything = () => {
  goToFullSearch(searchQuery.value);
};

const searchFromRecent = (recentTerm) => {
  searchQuery.value = recentTerm;
  goToFullSearch(recentTerm);
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

/* Emphasize the matched run of text in a suggestion. Uses the theme primary
   colour so it reads correctly in both light and dark themes. */
.search-hl {
  color: rgb(var(--v-theme-primary));
  font-weight: 700;
}

.search-item-title {
  white-space: normal;
}

.search-no-data {
  font-size: 0.875rem;
}
</style>
