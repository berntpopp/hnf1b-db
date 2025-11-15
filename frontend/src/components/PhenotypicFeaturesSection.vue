<template>
  <v-card variant="outlined" class="mb-4">
    <v-card-title class="bg-green-lighten-5">
      <v-icon left>mdi-dna</v-icon>
      Phenotypic Features
    </v-card-title>

    <v-card-text>
      <!-- Filter Select -->
      <v-select
        v-model="recommendationFilter"
        :items="filterOptions"
        label="Show phenotypes"
        density="compact"
        class="mb-4"
        style="max-width: 300px"
      />

      <!-- Loading State -->
      <div v-if="loading" class="text-center py-4">
        <v-progress-circular indeterminate color="primary" size="32" />
      </div>

      <!-- Legend -->
      <div v-else class="mb-4 d-flex align-center gap-4">
        <div class="text-caption d-flex align-center">
          <v-icon color="grey" size="small" class="mr-1">mdi-help-circle</v-icon>
          Unknown
        </div>
        <div class="text-caption d-flex align-center">
          <v-icon color="success" size="small" class="mr-1">mdi-plus-circle</v-icon>
          Present
        </div>
        <div class="text-caption d-flex align-center">
          <v-icon color="error" size="small" class="mr-1">mdi-minus-circle</v-icon>
          Excluded
        </div>
      </div>

      <!-- Two-Column Grouped Phenotypes -->
      <v-row v-if="!loading">
        <v-col
          v-for="(terms, groupName) in groupedByColumns"
          :key="groupName"
          cols="12"
          md="6"
          class="phenotype-column"
        >
          <div v-for="group in terms" :key="group.name" class="mb-6">
            <div class="text-h6 mb-2" :style="{ color: getGroupColor(group.name) }">
              <v-icon :color="getGroupColor(group.name)" class="mr-2">
                {{ getGroupIcon(group.name) }}
              </v-icon>
              {{ group.name }}
            </div>

            <v-list density="compact" class="mb-2">
              <v-list-item v-for="term in group.terms" :key="term.hpo_id" class="phenotype-item">
                <template #prepend>
                  <v-btn
                    :icon="getStateIcon(term.hpo_id)"
                    :color="getStateColor(term.hpo_id)"
                    variant="text"
                    size="small"
                    @click="cycleState(term)"
                  />
                </template>

                <v-list-item-title>
                  {{ term.label }}
                  <v-chip
                    v-if="term.recommendation === 'required'"
                    size="x-small"
                    color="error"
                    variant="flat"
                    class="ml-2"
                  >
                    Required
                  </v-chip>
                </v-list-item-title>

                <v-list-item-subtitle class="text-caption">
                  {{ term.hpo_id }}
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </div>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useGroupedHPO } from '@/composables/useGroupedHPO';

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(['update:modelValue']);

const { groups, loading, fetchGrouped } = useGroupedHPO();

const recommendationFilter = ref('all');
const filterOptions = [
  { title: 'All phenotypes', value: 'all' },
  { title: 'Required only', value: 'required' },
  { title: 'Recommended only', value: 'recommended' },
];

const SYSTEM_COLORS = {
  Kidney: '#1976D2',
  'Urinary tract': '#1976D2',
  Liver: '#388E3C',
  Pancreas: '#7B1FA2',
  Hormones: '#7B1FA2',
  'Electrolytes and uric acid': '#F57C00',
  Brain: '#5E35B1',
  Genital: '#00897B',
  Other: '#616161',
};

const SYSTEM_ICONS = {
  Kidney: 'mdi-kidney',
  'Urinary tract': 'mdi-water',
  Liver: 'mdi-bacteria-outline',
  Pancreas: 'mdi-stomach',
  Hormones: 'mdi-test-tube',
  'Electrolytes and uric acid': 'mdi-molecule',
  Brain: 'mdi-brain',
  Genital: 'mdi-human-male-female',
  Other: 'mdi-dots-horizontal',
};

const getGroupColor = (groupName) => SYSTEM_COLORS[groupName] || SYSTEM_COLORS.Other;
const getGroupIcon = (groupName) => SYSTEM_ICONS[groupName] || SYSTEM_ICONS.Other;

const filteredGroups = computed(() => {
  if (recommendationFilter.value === 'all') return groups.value;

  const filtered = {};
  Object.keys(groups.value).forEach((groupName) => {
    const filteredTerms = groups.value[groupName].filter(
      (term) => term.recommendation === recommendationFilter.value
    );
    if (filteredTerms.length > 0) {
      filtered[groupName] = filteredTerms;
    }
  });
  return filtered;
});

// Split groups into two columns for better layout
const groupedByColumns = computed(() => {
  const groupNames = Object.keys(filteredGroups.value);
  const midpoint = Math.ceil(groupNames.length / 2);

  return {
    left: groupNames.slice(0, midpoint).map((name) => ({
      name,
      terms: filteredGroups.value[name],
    })),
    right: groupNames.slice(midpoint).map((name) => ({
      name,
      terms: filteredGroups.value[name],
    })),
  };
});

// Get the state of a phenotype: 0 = unknown, 1 = present, 2 = excluded
const getState = (hpoId) => {
  const feature = props.modelValue.find((f) => f.type?.id === hpoId);
  if (!feature) return 0; // unknown
  return feature.excluded ? 2 : 1; // excluded or present
};

const getStateIcon = (hpoId) => {
  const state = getState(hpoId);
  if (state === 0) return 'mdi-help-circle';
  if (state === 1) return 'mdi-plus-circle';
  return 'mdi-minus-circle';
};

const getStateColor = (hpoId) => {
  const state = getState(hpoId);
  if (state === 0) return 'grey';
  if (state === 1) return 'success';
  return 'error';
};

// Cycle through states: unknown -> present -> excluded -> unknown
const cycleState = (term) => {
  const updated = [...props.modelValue];
  const index = updated.findIndex((f) => f.type?.id === term.hpo_id);
  const currentState = getState(term.hpo_id);

  if (currentState === 0) {
    // Unknown -> Present
    updated.push({
      type: { id: term.hpo_id, label: term.label },
      excluded: false,
    });
  } else if (currentState === 1) {
    // Present -> Excluded
    updated[index].excluded = true;
  } else {
    // Excluded -> Unknown (remove)
    updated.splice(index, 1);
  }

  emit('update:modelValue', updated);
};

onMounted(() => fetchGrouped());
</script>

<style scoped>
.phenotype-item {
  border-left: 3px solid transparent;
}
.phenotype-item:hover {
  background-color: rgba(0, 0, 0, 0.02);
}
.phenotype-column {
  min-height: 100px;
}
.gap-4 {
  gap: 16px;
}
</style>
