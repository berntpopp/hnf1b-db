<template>
  <div v-if="modelValue.length || canEdit" class="mb-4" data-testid="publication-specialty">
    <div class="d-flex align-center text-subtitle-2 text-medium-emphasis mb-1">
      Medical specialty
      <v-btn
        v-if="canEdit && !editing"
        icon="mdi-pencil"
        size="x-small"
        variant="text"
        class="ml-1"
        aria-label="Edit medical specialty"
        data-testid="specialty-edit-btn"
        @click="startEdit"
      />
    </div>

    <div v-if="!editing" class="d-flex flex-wrap ga-1">
      <v-chip v-for="s in modelValue" :key="s" color="primary" variant="tonal" size="small">
        {{ s }}
      </v-chip>
      <span v-if="!modelValue.length" class="text-body-2 text-medium-emphasis">
        Not yet curated
      </span>
    </div>

    <v-sheet v-else border rounded="lg" class="pa-3" data-testid="specialty-editor">
      <v-autocomplete
        v-model="draft"
        :items="vocabulary"
        :loading="loading"
        label="Specialties, most important first"
        multiple
        chips
        closable-chips
        density="compact"
        variant="outlined"
        hide-details
        data-testid="specialty-select"
      />

      <div class="mt-3">
        <div class="d-flex align-center text-caption text-medium-emphasis mb-2">
          <v-icon size="small" class="mr-1" aria-hidden="true">mdi-lightbulb-on-outline</v-icon>
          Suggested from the journal and first/last author affiliations
          <v-spacer />
          <v-btn
            v-if="suggestions.length"
            size="x-small"
            variant="text"
            color="primary"
            data-testid="specialty-use-all"
            @click="useAll"
          >
            Use suggestions
          </v-btn>
        </div>

        <v-progress-linear v-if="loading" indeterminate color="primary" rounded />
        <v-alert
          v-else-if="error"
          type="warning"
          variant="tonal"
          density="compact"
          class="text-body-2"
          data-testid="specialty-error"
        >
          {{ error }}
        </v-alert>
        <div v-else-if="!suggestions.length" class="text-body-2 text-medium-emphasis">
          No specialty signal in the journal or author affiliations.
        </div>
        <div v-else class="d-flex flex-wrap ga-2" data-testid="specialty-suggestions">
          <v-tooltip v-for="s in suggestions" :key="s.specialty" location="top">
            <template #activator="{ props: tip }">
              <v-chip
                v-bind="tip"
                :color="draft.includes(s.specialty) ? 'success' : 'primary'"
                :prepend-icon="draft.includes(s.specialty) ? 'mdi-check' : 'mdi-plus'"
                :aria-pressed="draft.includes(s.specialty)"
                variant="outlined"
                size="small"
                :data-testid="`specialty-suggestion-${s.specialty}`"
                @click="toggle(s.specialty)"
              >
                {{ s.specialty }}
                <span class="ml-1 text-medium-emphasis">{{ s.score }}</span>
              </v-chip>
            </template>
            {{ describe(s) }}
          </v-tooltip>
        </div>
      </div>

      <div class="d-flex justify-end ga-2 mt-3">
        <v-btn variant="text" :disabled="saving" @click="editing = false">Cancel</v-btn>
        <v-btn
          color="primary"
          variant="flat"
          :loading="saving"
          :disabled="loading"
          data-testid="specialty-save-btn"
          @click="save"
        >
          Save
        </v-btn>
      </div>
    </v-sheet>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { getPublicationSpecialty, updatePublicationSpecialty } from '@/api';
import { useAuthStore } from '@/stores/authStore';
import { formatApiError } from '@/utils/apiError';

const props = defineProps({
  pmid: { type: String, required: true },
  modelValue: { type: Array, default: () => [] },
});
const emit = defineEmits(['update:modelValue']);

const authStore = useAuthStore();
const canEdit = computed(() => authStore.isCurator);

const editing = ref(false);
const loading = ref(false);
const saving = ref(false);
const error = ref(null);
const draft = ref([]);
const vocabulary = ref([]);
const suggestions = ref([]);

const SOURCE_LABELS = {
  journal: 'journal',
  first_author: 'first author',
  last_author: 'last author',
};

function describe(s) {
  const sources = s.evidence.map((e) => SOURCE_LABELS[e] || e).join(', ');
  return `From ${sources} (score ${s.score})`;
}

async function startEdit() {
  editing.value = true;
  draft.value = [...props.modelValue];
  loading.value = true;
  error.value = null;
  try {
    const { data } = await getPublicationSpecialty(props.pmid);
    vocabulary.value = data.vocabulary;
    suggestions.value = data.suggestions;
    error.value = data.suggestion_error || null;
  } catch (err) {
    error.value = formatApiError(err, 'Could not load suggestions');
    window.logService?.error('Failed to load specialty suggestions', { error: err.message });
  } finally {
    loading.value = false;
  }
}

function toggle(name) {
  draft.value = draft.value.includes(name)
    ? draft.value.filter((s) => s !== name)
    : [...draft.value, name];
}

function useAll() {
  draft.value = suggestions.value.map((s) => s.specialty);
}

async function save() {
  saving.value = true;
  error.value = null;
  try {
    const { data } = await updatePublicationSpecialty(props.pmid, draft.value);
    emit('update:modelValue', data.medical_specialty);
    editing.value = false;
  } catch (err) {
    error.value = formatApiError(err, 'Could not save');
    window.logService?.error('Failed to save medical specialty', { error: err.message });
  } finally {
    saving.value = false;
  }
}
</script>
