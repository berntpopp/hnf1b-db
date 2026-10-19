<!-- src/components/curation/PhenotypeSuggestionDrawer.vue -->
<template>
  <div class="phenotype-suggestion-drawer-container">
    <v-btn
      color="primary"
      variant="tonal"
      prepend-icon="mdi-lightbulb-outline"
      data-testid="suggest-phenotypes-btn"
      :disabled="!pmid"
      @click="openDrawer"
    >
      Suggest Phenotypes from PMID
    </v-btn>

    <v-dialog
      v-model="isOpen"
      max-width="640"
      scrollable
      data-testid="phenotype-suggestion-drawer"
    >
      <v-card class="d-flex flex-column fill-height">
        <v-toolbar color="surface" density="compact" class="border-b px-4">
          <v-icon icon="mdi-lightbulb-outline" class="mr-2" color="primary" />
          <v-toolbar-title class="text-subtitle-1 font-weight-bold">
            Suggested Phenotypes (PMID: {{ cleanPmid }})
          </v-toolbar-title>
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="isOpen = false" />
        </v-toolbar>

        <div class="pa-4 flex-grow-1 overflow-y-auto">
          <!-- Loading state -->
          <div v-if="loading" class="text-center py-8">
            <v-progress-circular indeterminate color="primary" size="40" />
            <div class="mt-3 text-caption text-medium-emphasis">
              Scanning publication passages for HPO terms...
            </div>
          </div>

          <!-- Error state -->
          <v-alert
            v-else-if="error"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-4"
          >
            {{ error }}
          </v-alert>

          <!-- Empty state -->
          <v-alert
            v-else-if="suggestions.length === 0"
            type="info"
            variant="tonal"
            density="compact"
            class="mb-4"
          >
            No HPO phenotypes detected in publication passages or metadata for PMID {{ cleanPmid }}.
          </v-alert>

          <!-- Suggestions List -->
          <div v-else>
            <div class="d-flex justify-space-between align-center mb-3">
              <span class="text-caption text-medium-emphasis">
                {{ suggestions.length }} suggested term{{ suggestions.length > 1 ? 's' : '' }} found
              </span>
              <v-btn
                variant="text"
                density="compact"
                size="small"
                @click="toggleSelectAll"
              >
                {{ allSelected ? 'Deselect All' : 'Select All' }}
              </v-btn>
            </div>

            <v-card
              v-for="(item, idx) in suggestions"
              :key="idx"
              variant="outlined"
              class="mb-3 pa-3"
              :class="{ 'border-primary': selectedIndices.includes(idx) }"
            >
              <div class="d-flex align-start">
                <v-checkbox
                  v-model="selectedIndices"
                  :value="idx"
                  density="compact"
                  hide-details
                  class="mt-0 pt-0 mr-2"
                />
                <div class="flex-grow-1">
                  <div class="d-flex align-center justify-space-between mb-1">
                    <span class="font-weight-medium text-body-2">
                      {{ item.label }}
                    </span>
                    <v-chip
                      size="x-small"
                      :color="item.excluded ? 'error' : 'success'"
                      variant="flat"
                      class="text-uppercase font-weight-bold"
                    >
                      {{ item.excluded ? 'Excluded' : 'Present' }}
                    </v-chip>
                  </div>
                  <div class="text-caption text-medium-emphasis mb-2 d-flex align-center">
                    <span class="font-mono mr-2">{{ item.hpo_id }}</span>
                    <v-chip size="x-small" variant="outlined" density="compact">
                      {{ item.section }}
                    </v-chip>
                  </div>
                  <div class="text-caption bg-grey-lighten-4 pa-2 rounded font-italic">
                    "{{ item.sentence }}"
                  </div>
                </div>
              </div>
            </v-card>
          </div>
        </div>

        <div class="pa-4 border-t bg-surface">
          <v-btn
            block
            color="primary"
            :disabled="selectedIndices.length === 0"
            data-testid="accept-suggested-phenotypes-btn"
            @click="acceptSelected"
          >
            Accept Selected Phenotypes ({{ selectedIndices.length }})
          </v-btn>
        </div>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { apiClient } from '@/api';

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
  pmid: {
    type: String,
    default: '',
  },
  evidenceCodeItems: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(['update:modelValue']);

const isOpen = ref(false);
const loading = ref(false);
const error = ref(null);
const suggestions = ref([]);
const selectedIndices = ref([]);

const cleanPmid = computed(() => {
  if (!props.pmid) return '';
  return String(props.pmid).replace(/^PMID:/i, '').trim();
});

const allSelected = computed(() => {
  return (
    suggestions.value.length > 0 &&
    selectedIndices.value.length === suggestions.value.length
  );
});

function toggleSelectAll() {
  if (allSelected.value) {
    selectedIndices.value = [];
  } else {
    selectedIndices.value = suggestions.value.map((_, idx) => idx);
  }
}

async function fetchSuggestions() {
  if (!cleanPmid.value) return;
  loading.value = true;
  error.value = null;
  suggestions.value = [];
  selectedIndices.value = [];

  try {
    const response = await apiClient.get('/publications/passages/suggest-phenotypes', {
      params: { pmid: cleanPmid.value },
    });
    suggestions.value = response.data?.suggestions || [];
    selectedIndices.value = suggestions.value.map((_, idx) => idx);
  } catch (err) {
    error.value =
      err.response?.data?.detail || err.message || 'Failed to fetch suggestions';
    if (window.logService?.error) {
      window.logService.error('Failed to fetch phenotype suggestions', { error: err });
    }
  } finally {
    loading.value = false;
  }
}

function openDrawer() {
  isOpen.value = true;
  fetchSuggestions();
}

function acceptSelected() {
  const defaultEvidenceCode =
    props.evidenceCodeItems?.length > 0
      ? {
          id: props.evidenceCodeItems[0].id,
          label: props.evidenceCodeItems[0].label,
        }
      : {
          id: 'ECO:0000033',
          label: 'author statement supported by traceable reference',
        };

  const evidence = cleanPmid.value
    ? [
        {
          evidenceCode: defaultEvidenceCode,
          reference: {
            id: `PMID:${cleanPmid.value}`,
            description: `Extracted from PMID:${cleanPmid.value}`,
          },
        },
      ]
    : [];

  const existing = [...(props.modelValue || [])];
  const existingIds = new Set(
    existing.map((f) => f.type?.id).filter(Boolean)
  );

  for (const idx of selectedIndices.value) {
    const item = suggestions.value[idx];
    if (!item) continue;
    if (!existingIds.has(item.hpo_id)) {
      existing.push({
        type: {
          id: item.hpo_id,
          label: item.label,
        },
        excluded: Boolean(item.excluded),
        evidence: evidence,
        modifiers: [],
      });
      existingIds.add(item.hpo_id);
    }
  }

  emit('update:modelValue', existing);
  isOpen.value = false;
}
</script>

<style scoped>
.font-mono {
  font-family: monospace;
}
</style>
