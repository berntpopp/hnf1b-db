<template>
  <v-container fluid>
    <!-- Header -->
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center gap-4">
          <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" />
          <h2 class="text-h4">Results for "{{ searchQuery }}"</h2>
        </div>

        <!-- Tabs -->
        <v-tabs v-model="activeTab" color="primary" class="mt-4">
          <v-tab value="all">All ({{ summaryTotal }})</v-tab>
          <v-tab v-if="summary['Phenopacket']" value="Phenopacket">
            Phenopackets ({{ summary['Phenopacket'] }})
          </v-tab>
          <v-tab v-if="summary['Variant']" value="Variant">
            Variants ({{ summary['Variant'] }})
          </v-tab>
          <v-tab v-if="summary['Publication']" value="Publication">
            Publications ({{ summary['Publication'] }})
          </v-tab>
          <v-tab v-if="summary['Gene Feature']" value="Gene Feature">
            Gene Features ({{ summary['Gene Feature'] }})
          </v-tab>
        </v-tabs>
      </v-col>
    </v-row>

    <v-row class="mt-4">
      <v-col cols="12">
        <!-- Loading -->
        <div v-if="loading" class="d-flex justify-center align-center py-12">
          <v-progress-circular indeterminate color="primary" size="64" />
        </div>

        <v-window v-else v-model="activeTab">
          <v-window-item value="all">
            <!-- Best Match Section -->
            <div v-if="bestMatch" class="mb-6">
              <div class="text-overline mb-2 text-medium-emphasis">TOP RESULT</div>
              <v-card
                variant="outlined"
                :color="getTypeColor(bestMatch.type)"
                class="border-opacity-50"
              >
                <v-card-item>
                  <template #prepend>
                    <v-avatar :color="getTypeColor(bestMatch.type)" variant="tonal" rounded="0">
                      <v-icon size="large">{{ getTypeIcon(bestMatch.type) }}</v-icon>
                    </v-avatar>
                  </template>
                  <v-card-title class="text-h6">{{ bestMatch.label }}</v-card-title>
                  <v-card-subtitle class="opacity-100">
                    {{ bestMatch.type }}
                    <span v-if="bestMatch.subtype">• {{ bestMatch.subtype }}</span>
                  </v-card-subtitle>
                </v-card-item>
                <v-divider />
                <v-card-actions>
                  <v-spacer />
                  <v-btn
                    variant="text"
                    :to="getResultLink(bestMatch)"
                    append-icon="mdi-arrow-right"
                  >
                    View Details
                  </v-btn>
                </v-card-actions>
              </v-card>
            </div>

            <!-- Mixed Results List -->
            <div v-if="results.length > 0">
              <div v-if="bestMatch" class="text-overline mb-2 text-medium-emphasis">
                OTHER RESULTS
              </div>
              <v-list lines="two" bg-color="transparent">
                <v-list-item
                  v-for="item in filteredResults"
                  :key="item.id + item.type"
                  :to="getResultLink(item)"
                  rounded="lg"
                  class="mb-2 elevation-1 bg-surface"
                  border
                >
                  <template #prepend>
                    <v-avatar :color="getTypeColor(item.type)" variant="tonal">
                      <v-icon>{{ getTypeIcon(item.type) }}</v-icon>
                    </v-avatar>
                  </template>
                  <v-list-item-title class="font-weight-medium">{{ item.label }}</v-list-item-title>
                  <v-list-item-subtitle>
                    <v-chip size="x-small" label class="mr-2" :color="getTypeColor(item.type)">
                      {{ item.type }}
                    </v-chip>
                    <span v-if="item.subtype" class="text-body-2 text-medium-emphasis">{{
                      item.subtype
                    }}</span>
                    <span v-if="item.extra_info" class="text-body-2 text-medium-emphasis">
                      • {{ item.extra_info }}</span
                    >
                  </v-list-item-subtitle>
                  <template #append>
                    <v-icon size="small" color="grey-lighten-1">mdi-chevron-right</v-icon>
                  </template>
                </v-list-item>
              </v-list>
            </div>
          </v-window-item>

          <!-- Type Specific Tabs -->
          <v-window-item
            v-for="type in ['Phenopacket', 'Variant', 'Publication', 'Gene Feature']"
            :key="type"
            :value="type"
          >
            <v-list v-if="results.length > 0" lines="two" bg-color="transparent">
              <v-list-item
                v-for="item in results"
                :key="item.id + item.type"
                :to="getResultLink(item)"
                rounded="lg"
                class="mb-2 elevation-1 bg-surface"
                border
              >
                <template #prepend>
                  <v-avatar :color="getTypeColor(item.type)" variant="tonal">
                    <v-icon>{{ getTypeIcon(item.type) }}</v-icon>
                  </v-avatar>
                </template>
                <v-list-item-title class="font-weight-medium">{{ item.label }}</v-list-item-title>
                <v-list-item-subtitle>
                  <span v-if="item.subtype">{{ item.subtype }}</span>
                  <span v-if="item.extra_info"> • {{ item.extra_info }}</span>
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-window-item>
        </v-window>

        <!-- Pagination -->
        <div v-if="totalResults > 0" class="d-flex justify-center mt-6">
          <v-pagination
            v-model="currentPage"
            :length="totalPages"
            total-visible="7"
            rounded="circle"
          />
        </div>

        <!-- Empty State -->
        <div v-if="!loading && results.length === 0" class="text-center mt-12">
          <v-avatar color="grey-lighten-4" size="120" class="mb-6">
            <v-icon size="64" color="grey-lighten-1">mdi-magnify-remove-outline</v-icon>
          </v-avatar>
          <h3 class="text-h5 text-medium-emphasis">No results found for "{{ searchQuery }}"</h3>
          <p class="text-body-1 text-disabled mt-2">
            Try checking for typos or using different keywords.
          </p>
        </div>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { searchGlobal } from '@/api';

const route = useRoute();

// State
const activeTab = ref('all');
const results = ref([]);
const summary = ref({});
const totalResults = ref(0);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = 20;

// Computed
const searchQuery = computed(() => route.query.q || '');
const totalPages = computed(() => Math.ceil(totalResults.value / pageSize));
const summaryTotal = computed(() => Object.values(summary.value).reduce((a, b) => a + b, 0));

const bestMatch = computed(() => {
  if (activeTab.value !== 'all' || results.value.length === 0 || currentPage.value > 1) return null;
  // If the top result has a significantly higher score than the next, treat it as best match
  // For now, just pick the first one if it's a "definitive" type like Gene Feature or Variant
  const first = results.value[0];
  if (['Gene', 'Gene Feature', 'Variant'].includes(first.type)) return first;
  return null;
});

const filteredResults = computed(() => {
  if (bestMatch.value) {
    return results.value.slice(1);
  }
  return results.value;
});

// Methods
const fetchResults = async () => {
  if (!searchQuery.value) return;

  loading.value = true;
  try {
    const typeFilter = activeTab.value === 'all' ? null : activeTab.value;
    const { data } = await searchGlobal(searchQuery.value, currentPage.value, pageSize, typeFilter);

    results.value = data.results;
    summary.value = data.summary;
    totalResults.value = data.total;
  } catch (error) {
    window.logService.error('Search failed', { error: error.message });
    results.value = [];
    totalResults.value = 0;
  } finally {
    loading.value = false;
  }
};

const getTypeColor = (type) => {
  switch (type) {
    case 'Gene':
      return 'primary';
    case 'Gene Feature':
      return 'purple';
    case 'Variant':
      return 'error';
    case 'Phenopacket':
      return 'teal';
    case 'Publication':
      return 'orange';
    default:
      return 'grey';
  }
};

const getTypeIcon = (type) => {
  switch (type) {
    case 'Gene':
      return 'mdi-dna';
    case 'Gene Feature':
      return 'mdi-creation';
    case 'Variant':
      return 'mdi-flash';
    case 'Phenopacket':
      return 'mdi-account';
    case 'Publication':
      return 'mdi-book-open-page-variant';
    default:
      return 'mdi-file';
  }
};

const getResultLink = (item) => {
  switch (item.type) {
    case 'Phenopacket':
      return `/phenopackets/${item.id}`;
    case 'Variant':
      return { name: 'Variants', query: { query: item.label } };
    case 'Publication':
      return { name: 'Publications', query: { q: item.id } }; // PMID
    case 'Gene':
      return `/reference?q=${item.label}`;
    case 'Gene Feature':
      return `/reference?q=${item.label}`;
    default:
      return '#';
  }
};

// Watchers
watch([() => route.query.q, activeTab, currentPage], () => {
  fetchResults();
});

// Reset page on tab/query change
watch([() => route.query.q, activeTab], () => {
  currentPage.value = 1;
});

onMounted(fetchResults);
</script>

<style scoped>
.gap-4 {
  gap: 16px;
}
</style>
