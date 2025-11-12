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
    <v-expansion-panels v-if="facets.phenotypes.length > 0" class="mb-3">
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
  onFilterChange();
  if (window.logService) {
    window.logService.info('Cleared all faceted filters');
  }
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
