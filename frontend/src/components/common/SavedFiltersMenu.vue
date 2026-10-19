<template>
  <div class="saved-filters-menu-root d-inline-flex align-center ga-1">
    <!-- Copy Cohort Link Button -->
    <v-tooltip
      :text="copied ? 'Cohort link copied to clipboard!' : 'Copy shareable cohort link'"
      location="bottom"
    >
      <template #activator="{ props: tooltipProps }">
        <v-btn
          v-bind="tooltipProps"
          data-testid="copy-cohort-link-btn"
          size="small"
          variant="tonal"
          color="primary"
          :prepend-icon="copied ? 'mdi-check' : 'mdi-share-variant'"
          aria-label="Copy cohort link"
          @click="handleCopyLink"
        >
          {{ copied ? 'Copied!' : 'Copy Cohort Link' }}
        </v-btn>
      </template>
    </v-tooltip>

    <!-- Saved Filters Dropdown Menu -->
    <v-menu
      v-model="menuOpen"
      :close-on-content-click="false"
      location="bottom end"
      offset="8"
      :attach="attach"
    >
      <template #activator="{ props: menuProps }">
        <v-btn
          v-bind="menuProps"
          data-testid="saved-filters-menu-btn"
          size="small"
          variant="outlined"
          color="primary"
          prepend-icon="mdi-bookmark-outline"
          aria-label="Open saved filters menu"
        >
          Saved Filters
          <v-badge
            v-if="presets.length > 0"
            :content="presets.length"
            color="primary"
            inline
            class="ml-1"
          />
        </v-btn>
      </template>

      <v-card min-width="300" max-width="380" class="pa-3">
        <v-card-title class="text-subtitle-2 px-1 py-1 d-flex align-center justify-space-between">
          <span class="font-weight-medium">Saved Searches</span>
          <v-chip size="x-small" variant="text" color="grey">
            {{ presets.length }} {{ presets.length === 1 ? 'preset' : 'presets' }}
          </v-chip>
        </v-card-title>

        <v-divider class="my-2" />

        <!-- Save Preset Input -->
        <div class="mb-3">
          <div class="text-caption text-medium-emphasis mb-1">Save current filters:</div>
          <div class="d-flex ga-2">
            <v-text-field
              v-model="presetName"
              data-testid="save-filter-preset-input"
              placeholder="Preset name..."
              density="compact"
              variant="outlined"
              hide-details
              class="flex-grow-1"
              @keyup.enter="handleSavePreset"
            />
            <v-btn
              data-testid="save-filter-preset-btn"
              color="primary"
              size="small"
              variant="flat"
              :disabled="!presetName.trim()"
              @click="handleSavePreset"
            >
              Save
            </v-btn>
          </div>
        </div>

        <v-divider class="my-2" />

        <!-- Presets List -->
        <div class="presets-section">
          <div class="text-caption text-medium-emphasis mb-1">Saved presets:</div>
          <div
            v-if="presets.length === 0"
            class="text-caption text-medium-emphasis py-2 text-center"
            data-testid="no-presets-message"
          >
            No saved filter presets yet.
          </div>
          <v-list v-else density="compact" class="pa-0">
            <v-list-item
              v-for="preset in presets"
              :key="preset.name"
              class="px-2 rounded mb-1"
              data-testid="preset-item"
              @click="handleApplyPreset(preset)"
            >
              <template #prepend>
                <v-icon size="small" color="primary">mdi-filter-variant</v-icon>
              </template>
              <v-list-item-title class="text-body-2 font-weight-medium">
                {{ preset.name }}
              </v-list-item-title>
              <v-list-item-subtitle
                v-if="formatFilterSummary(preset.filters)"
                class="text-caption text-truncate"
              >
                {{ formatFilterSummary(preset.filters) }}
              </v-list-item-subtitle>
              <template #append>
                <v-btn
                  icon="mdi-delete-outline"
                  size="x-small"
                  variant="text"
                  color="error"
                  data-testid="delete-preset-btn"
                  aria-label="Delete preset"
                  title="Delete preset"
                  @click.stop="handleDeletePreset(preset.name)"
                />
              </template>
            </v-list-item>
          </v-list>
        </div>
      </v-card>
    </v-menu>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useSavedFilters } from '@/composables/useSavedFilters';

const props = defineProps({
  scopeKey: {
    type: String,
    required: true,
  },
  currentFilters: {
    type: Object,
    default: () => ({}),
  },
  attach: {
    type: [Boolean, String],
    default: false,
  },
});

const emit = defineEmits(['apply', 'save', 'delete']);

const menuOpen = ref(false);
const presetName = ref('');

const { presets, copied, savePreset, deletePreset, copyShareableUrl } = useSavedFilters(
  props.scopeKey
);

function formatFilterSummary(filters) {
  if (!filters || typeof filters !== 'object') return '';
  const entries = Object.entries(filters).filter(
    ([, v]) => v !== null && v !== undefined && v !== ''
  );
  if (entries.length === 0) return 'No filters';
  return entries.map(([k, v]) => `${k}: ${v}`).join(', ');
}

function handleSavePreset() {
  const name = presetName.value.trim();
  if (!name) return;
  const saved = savePreset(name, props.currentFilters);
  if (saved) {
    presetName.value = '';
    emit('save', saved);
  }
}

function handleApplyPreset(preset) {
  if (!preset) return;
  emit('apply', preset.filters);
  menuOpen.value = false;
}

function handleDeletePreset(name) {
  deletePreset(name);
  emit('delete', name);
}

async function handleCopyLink() {
  await copyShareableUrl();
}
</script>

<style scoped>
.saved-filters-menu-root {
  display: inline-flex;
}
</style>
