<template>
  <v-card class="pa-4">
    <v-card-title class="text-h6 px-0">Filters</v-card-title>

    <!-- Sex Filter -->
    <v-expansion-panels class="mb-3">
      <v-expansion-panel>
        <v-expansion-panel-title>
          <div class="d-flex justify-space-between align-center" style="width: 100%">
            <span>Sex</span>
            <v-chip v-if="selectedFilters.sex.length > 0" size="small" color="primary">
              {{ selectedFilters.sex.length }}
            </v-chip>
          </div>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-checkbox
            v-for="option in facets.sex"
            :key="option.value"
            v-model="selectedFilters.sex"
            :label="`${option.label} (${option.count})`"
            :value="option.value"
            density="compact"
            hide-details
            @update:model-value="onFilterChange"
          />
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- Pathogenicity Filter -->
    <v-expansion-panels v-if="facets.pathogenicity.length > 0" class="mb-3">
      <v-expansion-panel>
        <v-expansion-panel-title>
          <div class="d-flex justify-space-between align-center" style="width: 100%">
            <span>Pathogenicity</span>
            <v-chip v-if="selectedFilters.pathogenicity.length > 0" size="small" color="primary">
              {{ selectedFilters.pathogenicity.length }}
            </v-chip>
          </div>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-checkbox
            v-for="option in facets.pathogenicity"
            :key="option.value"
            v-model="selectedFilters.pathogenicity"
            :label="`${option.label} (${option.count})`"
            :value="option.value"
            density="compact"
            hide-details
            @update:model-value="onFilterChange"
          />
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- Genes Filter -->
    <v-expansion-panels v-if="facets.genes.length > 0" class="mb-3">
      <v-expansion-panel>
        <v-expansion-panel-title>
          <div class="d-flex justify-space-between align-center" style="width: 100%">
            <span>Genes</span>
            <v-chip v-if="selectedFilters.genes.length > 0" size="small" color="primary">
              {{ selectedFilters.genes.length }}
            </v-chip>
          </div>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-checkbox
            v-for="option in facets.genes.slice(0, 10)"
            :key="option.value"
            v-model="selectedFilters.genes"
            :label="`${option.label} (${option.count})`"
            :value="option.value"
            density="compact"
            hide-details
            @update:model-value="onFilterChange"
          />
          <v-btn
            v-if="facets.genes.length > 10"
            variant="text"
            size="small"
            class="mt-2"
            @click="showAllGenes = !showAllGenes"
          >
            {{ showAllGenes ? 'Show Less' : `Show ${facets.genes.length - 10} More` }}
          </v-btn>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- Phenotypes Filter -->
    <v-expansion-panels class="mb-3">
      <v-expansion-panel>
        <v-expansion-panel-title>
          <div class="d-flex justify-space-between align-center" style="width: 100%">
            <span>Phenotypes</span>
            <v-chip v-if="selectedFilters.phenotypes.length > 0" size="small" color="primary">
              {{ selectedFilters.phenotypes.length }}
            </v-chip>
          </div>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <!-- HPO Autocomplete Search -->
          <v-autocomplete
            v-model="selectedPhenotype"
            :items="phenotypeSuggestions"
            :loading="loadingPhenotypes"
            :search="phenotypeSearchQuery"
            item-title="label"
            item-value="hpo_id"
            label="Search HPO terms..."
            placeholder="e.g., stage 5 chronic kidney disease"
            density="compact"
            variant="outlined"
            clearable
            hide-details
            class="mb-3"
            @update:search="onPhenotypeSearch"
            @update:model-value="onPhenotypeSelect"
          >
            <template #item="{ props, item }">
              <v-list-item v-bind="props" :title="item.raw.label" :subtitle="item.raw.hpo_id" />
            </template>
          </v-autocomplete>

          <!-- Selected Phenotypes as Chips -->
          <div v-if="selectedFilters.phenotypes.length > 0" class="mb-3">
            <v-chip
              v-for="hpoId in selectedFilters.phenotypes"
              :key="hpoId"
              size="small"
              closable
              class="mr-1 mb-1"
              @click:close="removePhenotype(hpoId)"
            >
              {{ getPhenotypeLabel(hpoId) }}
            </v-chip>
          </div>

          <!-- Top Phenotypes from Facets -->
          <div v-if="facets.phenotypes.length > 0">
            <v-divider class="mb-2" />
            <div class="text-caption text-grey mb-2">Top phenotypes in results:</div>
            <v-checkbox
              v-for="option in facets.phenotypes.slice(0, 10)"
              :key="option.value"
              v-model="selectedFilters.phenotypes"
              :label="`${option.label} (${option.count})`"
              :value="option.value"
              density="compact"
              hide-details
              @update:model-value="onFilterChange"
            />
            <v-btn
              v-if="facets.phenotypes.length > 10"
              variant="text"
              size="small"
              class="mt-2"
              @click="showAllPhenotypes = !showAllPhenotypes"
            >
              {{ showAllPhenotypes ? 'Show Less' : `Show ${facets.phenotypes.length - 10} More` }}
            </v-btn>
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- Clear All Button -->
    <v-btn
      block
      variant="outlined"
      color="error"
      class="mt-4"
      :disabled="!hasActiveFilters"
      @click="clearAllFilters"
    >
      Clear All Filters
    </v-btn>
  </v-card>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { getHpoAutocomplete } from '@/api';
import { debounce } from '@/utils/debounce';

const props = defineProps({
  facets: {
    type: Object,
    required: true,
    default: () => ({
      sex: [],
      pathogenicity: [],
      genes: [],
      phenotypes: [],
    }),
  },
  modelValue: {
    type: Object,
    default: () => ({
      sex: [],
      pathogenicity: [],
      genes: [],
      phenotypes: [],
    }),
  },
});

const emit = defineEmits(['update:modelValue', 'filter-change']);

const showAllGenes = ref(false);
const showAllPhenotypes = ref(false);

// HPO autocomplete state
const selectedPhenotype = ref(null);
const phenotypeSearchQuery = ref('');
const phenotypeSuggestions = ref([]);
const loadingPhenotypes = ref(false);
const phenotypeLabels = ref(new Map());

const selectedFilters = ref({
  sex: [],
  pathogenicity: [],
  genes: [],
  phenotypes: [],
  ...props.modelValue,
});

const hasActiveFilters = computed(() => {
  return (
    selectedFilters.value.sex.length > 0 ||
    selectedFilters.value.pathogenicity.length > 0 ||
    selectedFilters.value.genes.length > 0 ||
    selectedFilters.value.phenotypes.length > 0
  );
});

const onFilterChange = () => {
  emit('update:modelValue', selectedFilters.value);
  emit('filter-change', selectedFilters.value);
};

const clearAllFilters = () => {
  selectedFilters.value = {
    sex: [],
    pathogenicity: [],
    genes: [],
    phenotypes: [],
  };
  phenotypeLabels.value.clear();
  onFilterChange();
  if (window.logService) {
    window.logService.info('Cleared all faceted filters');
  }
};

// HPO autocomplete functions
const fetchPhenotypeSuggestions = async (query) => {
  if (!query || query.length < 2) {
    phenotypeSuggestions.value = [];
    return;
  }

  loadingPhenotypes.value = true;
  try {
    const response = await getHpoAutocomplete(query);
    phenotypeSuggestions.value = response.data.data || [];
    if (window.logService) {
      window.logService.debug('HPO autocomplete results', {
        query,
        count: phenotypeSuggestions.value.length,
      });
    }
  } catch (error) {
    if (window.logService) {
      window.logService.error('HPO autocomplete failed', { error: error.message });
    }
    phenotypeSuggestions.value = [];
  } finally {
    loadingPhenotypes.value = false;
  }
};

const debouncedFetchPhenotypes = debounce(fetchPhenotypeSuggestions, 300);

const onPhenotypeSearch = (query) => {
  phenotypeSearchQuery.value = query;
  debouncedFetchPhenotypes(query);
};

const onPhenotypeSelect = (hpoId) => {
  if (!hpoId) return;

  // Add to selected filters if not already present
  if (!selectedFilters.value.phenotypes.includes(hpoId)) {
    selectedFilters.value.phenotypes.push(hpoId);

    // Store label for display
    const suggestion = phenotypeSuggestions.value.find((s) => s.hpo_id === hpoId);
    if (suggestion) {
      phenotypeLabels.value.set(hpoId, suggestion.label);
    }

    onFilterChange();
    if (window.logService) {
      window.logService.info('Added phenotype filter', { hpoId, label: suggestion?.label });
    }
  }

  // Clear autocomplete
  selectedPhenotype.value = null;
  phenotypeSearchQuery.value = '';
  phenotypeSuggestions.value = [];
};

const removePhenotype = (hpoId) => {
  selectedFilters.value.phenotypes = selectedFilters.value.phenotypes.filter((id) => id !== hpoId);
  phenotypeLabels.value.delete(hpoId);
  onFilterChange();
  if (window.logService) {
    window.logService.info('Removed phenotype filter', { hpoId });
  }
};

const getPhenotypeLabel = (hpoId) => {
  // First check stored labels
  if (phenotypeLabels.value.has(hpoId)) {
    return phenotypeLabels.value.get(hpoId);
  }

  // Then check facets
  const facet = props.facets.phenotypes.find((p) => p.value === hpoId);
  if (facet) {
    phenotypeLabels.value.set(hpoId, facet.label);
    return facet.label;
  }

  // Fallback to HPO ID
  return hpoId;
};

// Watch for external changes to modelValue
watch(
  () => props.modelValue,
  (newValue) => {
    selectedFilters.value = { ...selectedFilters.value, ...newValue };
  },
  { deep: true }
);
</script>

<style scoped>
.v-expansion-panel-title {
  min-height: 48px;
}

.v-expansion-panel-text :deep(.v-expansion-panel-text__wrapper) {
  padding: 8px 16px;
}
</style>
