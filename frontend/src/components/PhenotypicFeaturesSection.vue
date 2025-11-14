<template>
  <v-card variant="outlined" class="phenotypic-features-section">
    <v-card-title class="d-flex align-center bg-green-lighten-5">
      <v-icon left>mdi-dna</v-icon>
      Phenotypic Features
      <v-spacer />
      <v-chip v-if="selectedCount > 0" color="primary" size="small">
        {{ selectedCount }} selected
      </v-chip>
    </v-card-title>

    <v-card-text>
      <!-- Loading State -->
      <div v-if="loading" class="text-center py-8">
        <v-progress-circular indeterminate color="primary" />
        <div class="mt-4 text-body-2">Loading phenotype groups...</div>
      </div>

      <!-- Error State -->
      <v-alert v-else-if="error" type="error" variant="tonal" class="mb-4">
        {{ error }}
      </v-alert>

      <!-- Filter Controls -->
      <div v-else class="mb-4">
        <v-btn-toggle v-model="recommendationFilter" variant="outlined" divided mandatory>
          <v-btn value="all" size="small">All Phenotypes</v-btn>
          <v-btn value="required" size="small">Required Only</v-btn>
          <v-btn value="recommended" size="small">Recommended Only</v-btn>
        </v-btn-toggle>
      </div>

      <!-- System-Grouped Phenotypes -->
      <v-expansion-panels v-if="!loading && !error" multiple>
        <v-expansion-panel
          v-for="(terms, groupName) in filteredGroups"
          :key="groupName"
          :class="`group-${getGroupClass(groupName)}`"
        >
          <v-expansion-panel-title>
            <div class="d-flex align-center w-100">
              <v-icon :color="getGroupColor(groupName)" class="mr-3">
                {{ getGroupIcon(groupName) }}
              </v-icon>
              <span class="font-weight-medium" :style="{ color: getGroupColor(groupName) }">
                {{ groupName }}
              </span>
              <v-spacer />
              <v-chip size="x-small" :color="getGroupColor(groupName)" variant="flat" class="mr-2">
                {{ terms.length }} terms
              </v-chip>
              <v-chip
                v-if="getGroupSelectionCount(groupName) > 0"
                size="x-small"
                color="success"
                variant="flat"
              >
                {{ getGroupSelectionCount(groupName) }} selected
              </v-chip>
            </div>
          </v-expansion-panel-title>

          <v-expansion-panel-text>
            <v-list density="compact">
              <v-list-item v-for="term in terms" :key="term.hpo_id" class="phenotype-item">
                <template #prepend>
                  <v-checkbox-btn
                    :model-value="getFeatureStatus(term.hpo_id)"
                    :indeterminate="getFeatureStatus(term.hpo_id) === 'excluded'"
                    :color="
                      getFeatureStatus(term.hpo_id) === 'observed'
                        ? 'success'
                        : getFeatureStatus(term.hpo_id) === 'excluded'
                          ? 'error'
                          : 'grey'
                    "
                    @update:model-value="toggleFeature(term, $event)"
                  />
                </template>

                <v-list-item-title class="d-flex align-center">
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
                  <v-chip
                    v-else-if="term.recommendation === 'recommended'"
                    size="x-small"
                    color="warning"
                    variant="flat"
                    class="ml-2"
                  >
                    Recommended
                  </v-chip>
                </v-list-item-title>

                <v-list-item-subtitle class="text-caption">
                  {{ term.hpo_id }}
                  <span v-if="term.category"> • {{ term.category }}</span>
                </v-list-item-subtitle>

                <template v-if="term.description" #append>
                  <v-tooltip location="top">
                    <template #activator="{ props: tooltipProps }">
                      <v-icon v-bind="tooltipProps" size="small" color="grey">
                        mdi-information-outline
                      </v-icon>
                    </template>
                    {{ term.description }}
                  </v-tooltip>
                </template>
              </v-list-item>
            </v-list>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>

      <!-- Manual Entry Option -->
      <v-divider class="my-4" />
      <div class="d-flex align-center">
        <v-btn
          variant="text"
          color="primary"
          prepend-icon="mdi-plus"
          size="small"
          @click="showManualEntry = !showManualEntry"
        >
          Add custom phenotype
        </v-btn>
      </div>

      <v-expand-transition>
        <div v-show="showManualEntry" class="mt-4">
          <HPOAutocomplete
            v-model="customTerm"
            label="Search for additional HPO term"
            hint="Search for phenotypes not in the recommended list"
          />
          <v-btn v-if="customTerm" color="primary" size="small" class="mt-2" @click="addCustomTerm">
            Add to phenotypes
          </v-btn>
        </div>
      </v-expand-transition>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useGroupedHPO } from '@/composables/useGroupedHPO';
import HPOAutocomplete from '@/components/HPOAutocomplete.vue';

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(['update:modelValue']);

// Composables
const { groups, loading, error, fetchGrouped } = useGroupedHPO();

// Local state
const recommendationFilter = ref('all');
const showManualEntry = ref(false);
const customTerm = ref(null);

// System color mapping (Material Design 3)
const SYSTEM_COLORS = {
  Kidney: '#1976D2', // Blue
  'Urinary tract': '#1976D2', // Blue (related to kidney)
  Liver: '#388E3C', // Green
  Pancreas: '#7B1FA2', // Purple
  Hormones: '#7B1FA2', // Purple (related to pancreas/endocrine)
  'Electrolytes and uric acid': '#F57C00', // Orange (metabolic)
  Metabolic: '#F57C00', // Orange
  Cardiac: '#C62828', // Red
  Brain: '#5E35B1', // Deep Purple
  Neurological: '#5E35B1', // Deep Purple
  Genital: '#00897B', // Teal
  Other: '#616161', // Gray
};

// System icon mapping
const SYSTEM_ICONS = {
  Kidney: 'mdi-kidney',
  'Urinary tract': 'mdi-water',
  Liver: 'mdi-bacteria-outline',
  Pancreas: 'mdi-stomach',
  Hormones: 'mdi-test-tube',
  'Electrolytes and uric acid': 'mdi-molecule',
  Metabolic: 'mdi-molecule',
  Cardiac: 'mdi-heart',
  Brain: 'mdi-brain',
  Neurological: 'mdi-brain',
  Genital: 'mdi-human-male-female',
  Other: 'mdi-dots-horizontal',
};

// Get color for group
const getGroupColor = (groupName) => {
  return SYSTEM_COLORS[groupName] || SYSTEM_COLORS.Other;
};

// Get icon for group
const getGroupIcon = (groupName) => {
  return SYSTEM_ICONS[groupName] || SYSTEM_ICONS.Other;
};

// Get CSS class for group
const getGroupClass = (groupName) => {
  return groupName.toLowerCase().replace(/\s+/g, '-');
};

// Filter groups by recommendation
const filteredGroups = computed(() => {
  if (recommendationFilter.value === 'all') {
    return groups.value;
  }

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

// Get feature status (observed/excluded/unknown)
const getFeatureStatus = (hpoId) => {
  const feature = props.modelValue.find((f) => f.type?.id === hpoId);
  if (!feature) return null;
  return feature.excluded ? 'excluded' : 'observed';
};

// Toggle feature (tri-state: unchecked → checked → indeterminate → unchecked)
const toggleFeature = (term, _checked) => {
  const currentStatus = getFeatureStatus(term.hpo_id);
  const updatedFeatures = [...props.modelValue];

  // Remove existing if present
  const existingIndex = updatedFeatures.findIndex((f) => f.type?.id === term.hpo_id);
  if (existingIndex !== -1) {
    updatedFeatures.splice(existingIndex, 1);
  }

  // Add with new status
  if (currentStatus === null) {
    // null → observed (checked)
    updatedFeatures.push({
      type: {
        id: term.hpo_id,
        label: term.label,
      },
      excluded: false,
    });
  } else if (currentStatus === 'observed') {
    // observed → excluded (indeterminate)
    updatedFeatures.push({
      type: {
        id: term.hpo_id,
        label: term.label,
      },
      excluded: true,
    });
  }
  // excluded → null (unchecked) - already removed above

  emit('update:modelValue', updatedFeatures);

  window.logService.debug('Toggled phenotypic feature', {
    hpoId: term.hpo_id,
    label: term.label,
    newStatus:
      currentStatus === null ? 'observed' : currentStatus === 'observed' ? 'excluded' : 'removed',
  });
};

// Get selection count for group
const getGroupSelectionCount = (groupName) => {
  const groupTerms = groups.value[groupName] || [];
  return groupTerms.filter((term) => getFeatureStatus(term.hpo_id) !== null).length;
};

// Total selected count
const selectedCount = computed(() => {
  return props.modelValue.length;
});

// Add custom term
const addCustomTerm = () => {
  if (!customTerm.value) return;

  const updatedFeatures = [...props.modelValue];
  const existingIndex = updatedFeatures.findIndex((f) => f.type?.id === customTerm.value.id);

  if (existingIndex === -1) {
    updatedFeatures.push({
      type: {
        id: customTerm.value.id,
        label: customTerm.value.label,
      },
      excluded: false,
    });

    emit('update:modelValue', updatedFeatures);

    window.logService.info('Added custom phenotypic feature', {
      hpoId: customTerm.value.id,
      label: customTerm.value.label,
    });
  }

  customTerm.value = null;
  showManualEntry.value = false;
};

// Load grouped HPO terms on mount
onMounted(async () => {
  try {
    await fetchGrouped();
  } catch (err) {
    window.logService.error('Failed to load grouped HPO terms', { error: err.message });
  }
});

// Reload when filter changes
watch(recommendationFilter, async (newFilter) => {
  if (newFilter !== 'all') {
    try {
      await fetchGrouped(newFilter);
    } catch (err) {
      window.logService.error('Failed to reload grouped HPO terms', { error: err.message });
    }
  } else {
    try {
      await fetchGrouped();
    } catch (err) {
      window.logService.error('Failed to reload grouped HPO terms', { error: err.message });
    }
  }
});
</script>

<style scoped>
.phenotypic-features-section {
  margin-bottom: 1rem;
}

.phenotype-item {
  border-left: 3px solid transparent;
  transition: border-color 0.2s ease;
}

.phenotype-item:hover {
  background-color: rgba(0, 0, 0, 0.02);
}

/* Color-coded borders for groups */
.group-kidney .phenotype-item:hover {
  border-left-color: #1976d2;
}

.group-liver .phenotype-item:hover {
  border-left-color: #388e3c;
}

.group-pancreas .phenotype-item:hover,
.group-hormones .phenotype-item:hover {
  border-left-color: #7b1fa2;
}

.group-electrolytes-and-uric-acid .phenotype-item:hover,
.group-metabolic .phenotype-item:hover {
  border-left-color: #f57c00;
}

.group-brain .phenotype-item:hover,
.group-neurological .phenotype-item:hover {
  border-left-color: #5e35b1;
}

.group-cardiac .phenotype-item:hover {
  border-left-color: #c62828;
}

.group-genital .phenotype-item:hover {
  border-left-color: #00897b;
}

.group-urinary-tract .phenotype-item:hover {
  border-left-color: #1976d2;
}

.group-other .phenotype-item:hover {
  border-left-color: #616161;
}
</style>
