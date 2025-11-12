<template>
  <v-container>
    <v-row>
      <v-col cols="12">
        <h2>Search Results</h2>
        <v-chip-group v-if="Object.keys(filters).length > 0">
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
        <p v-else class="text-grey">No filters applied. Showing all phenopackets.</p>
      </v-col>
    </v-row>

    <v-row v-if="loading">
      <v-col cols="12" class="text-center">
        <v-progress-circular indeterminate color="primary" />
        <p class="mt-2">Searching phenopackets...</p>
      </v-col>
    </v-row>

    <v-row v-else>
      <v-col cols="12">
        <v-data-table
          :headers="headers"
          :items="results"
          :items-length="totalResults"
          class="elevation-1"
          @click:row="navigateToPhenopacket"
        >
          <template #item.search_rank="{ item }">
            <v-chip v-if="item.search_rank" color="green" small>
              {{ (item.search_rank * 100).toFixed(1) }}% match
            </v-chip>
          </template>
          <template #item.subject.id="{ item }">
            <router-link :to="`/phenopackets/${item.id}`">{{ item.subject.id }}</router-link>
          </template>
        </v-data-table>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { searchPhenopackets } from '@/api';

const route = useRoute();
const router = useRouter();

const filters = computed(() => route.query);
const results = ref([]);
const loading = ref(false);
const totalResults = ref(0);

const headers = [
  { title: 'ID', value: 'subject.id' },
  { title: 'Sex', value: 'subject.sex' },
  { title: 'Relevance', value: 'search_rank' },
];

const fetchResults = async () => {
  loading.value = true;
  try {
    const { data } = await searchPhenopackets(filters.value);
    results.value = data.data.map((pp) => ({
      ...pp.attributes,
      id: pp.id, // include the top-level phenopacket ID
      search_rank: pp.meta?.search_rank,
    }));
    totalResults.value = data.meta.total;
  } catch (error) {
    if (window.logService) {
      window.logService.error('Search failed', { error: error.message });
    } else {
      console.error('Search failed', { error: error.message });
    }
  } finally {
    loading.value = false;
  }
};

const removeFilter = (key) => {
  const newQuery = { ...route.query };
  delete newQuery[key];
  router.push({ query: newQuery });
};

const navigateToPhenopacket = (event, { item }) => {
  if (item && item.id) {
    router.push(`/phenopackets/${item.id}`);
  }
};

// Fetch results on component mount
onMounted(fetchResults);

// Watch for changes in query parameters and re-fetch results
watch(() => route.query, fetchResults, { deep: true });
</script>

<style scoped>
.v-data-table :deep(tbody tr) {
  cursor: pointer;
}
</style>
