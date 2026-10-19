<!--
  Phenotypes section content for the curation console (curation console
  design spec §3.4; plan Task 7). Renders inside PhenopacketCreateEdit.vue's
  <CurationSection id="phenotypes">, which already provides the section
  chrome (title, completeness badge, collapse) -- this component owns no
  card of its own, and no hardcoded bg-*-lighten-* (design floor §5).
-->
<template>
  <div>
    <div>
      <!-- Keyboard-First HPO Quick-Add Bar (#549) -->
      <v-card variant="outlined" class="pa-3 mb-4" density="compact">
        <div class="d-flex align-center flex-wrap gap-2 mb-2">
          <div class="text-subtitle-2 font-weight-bold d-flex align-center">
            <v-icon size="small" color="primary" class="mr-1">mdi-lightning-bolt</v-icon>
            Quick-Add Phenotype
          </div>
          <v-chip size="x-small" variant="tonal" color="primary"> Cmd+K or / to focus </v-chip>
          <v-chip size="x-small" variant="tonal" color="success"> Enter = Present </v-chip>
          <v-chip size="x-small" variant="tonal" color="error"> Shift+Enter = Excluded </v-chip>
          <v-chip size="x-small" variant="tonal" color="grey"> Alt+B/U/R/L = Laterality </v-chip>
        </div>

        <div class="d-flex flex-wrap align-center gap-2">
          <div class="flex-grow-1" style="min-width: 260px; position: relative">
            <v-text-field
              ref="quickAddInputRef"
              v-model="searchQuery"
              data-testid="hpo-quick-add-input"
              :input-props="{ 'data-testid': 'hpo-quick-add-input' }"
              placeholder="Search HPO (e.g. HP:0000107 or Renal cyst)..."
              density="compact"
              variant="outlined"
              prepend-inner-icon="mdi-magnify"
              clearable
              hide-details
              autocomplete="off"
              @update:model-value="onSearchInput"
              @keydown="handleInputKeydown"
            />

            <!-- Autocomplete Suggestion Dropdown List -->
            <v-card
              v-if="suggestions.length > 0"
              class="quick-add-suggestions-card"
              data-testid="hpo-quick-add-suggestions"
              elevation="4"
            >
              <v-list density="compact" class="pa-0">
                <v-list-item
                  v-for="(suggestion, idx) in suggestions"
                  :key="suggestion.id"
                  :active="idx === activeIndex"
                  :data-testid="`hpo-suggestion-${suggestion.id}`"
                  class="quick-add-suggestion-item"
                  @click="addSuggestedTerm(suggestion, false)"
                >
                  <template #prepend>
                    <v-chip
                      size="x-small"
                      :color="idx === activeIndex ? 'primary' : 'default'"
                      class="mr-2"
                    >
                      {{ suggestion.id }}
                    </v-chip>
                  </template>

                  <v-list-item-title class="font-weight-medium">
                    {{ suggestion.label }}
                  </v-list-item-title>

                  <template #append>
                    <div class="d-flex align-center gap-1">
                      <v-btn
                        size="x-small"
                        variant="tonal"
                        color="success"
                        data-testid="add-present-btn"
                        title="Add as Present (Enter)"
                        @click.stop="addSuggestedTerm(suggestion, false)"
                      >
                        + Present
                      </v-btn>
                      <v-btn
                        size="x-small"
                        variant="tonal"
                        color="error"
                        data-testid="add-excluded-btn"
                        title="Add as Excluded (Shift+Enter)"
                        @click.stop="addSuggestedTerm(suggestion, true)"
                      >
                        - Excluded
                      </v-btn>
                    </div>
                  </template>
                </v-list-item>
              </v-list>
            </v-card>
          </div>

          <!-- Quick Laterality Selector -->
          <v-select
            v-model="quickLaterality"
            :items="quickLateralityOptions"
            item-title="title"
            item-value="value"
            data-testid="quick-add-laterality-select"
            label="Laterality"
            density="compact"
            variant="outlined"
            clearable
            hide-details
            style="max-width: 170px"
          />

          <!-- Quick Onset Input -->
          <v-text-field
            v-model="quickOnset"
            data-testid="quick-add-onset-input"
            :input-props="{ 'data-testid': 'quick-add-onset-input' }"
            placeholder="Onset (P20Y)"
            label="Onset"
            density="compact"
            variant="outlined"
            clearable
            hide-details
            style="max-width: 140px"
            @keydown="handleInputKeydown"
          />
        </div>
      </v-card>

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

            <!-- CKD Stages: Dropdown Select (mutually exclusive) -->
            <v-select
              v-if="group.name === 'CKD Stages'"
              :model-value="getSelectedCKDStage(group.terms)"
              :items="group.terms"
              item-title="label"
              item-value="hpo_id"
              label="Select CKD Stage"
              density="compact"
              clearable
              @update:model-value="selectCKDStage(group.terms, $event)"
            >
              <template #item="{ item, props: itemProps }">
                <v-list-item v-bind="itemProps">
                  <v-list-item-subtitle class="text-caption">
                    {{ item.raw.hpo_id }}
                  </v-list-item-subtitle>
                </v-list-item>
              </template>
            </v-select>

            <!-- Regular phenotypes: Tri-state icons -->
            <v-list v-else density="compact" class="mb-2">
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

                <!-- Per-feature laterality (curation console Task 7, design
                     spec §3.4): only for a present (non-excluded) term the
                     live /ontology/laterality-policy fetch admits at least
                     one modifier for. Single-select -- laterality is
                     mutually exclusive per term. -->
                <template v-if="showLaterality(term.hpo_id)" #append>
                  <v-select
                    :model-value="getModifierValue(term.hpo_id)"
                    :items="lateralityOptionsFor(term.hpo_id)"
                    item-title="label"
                    item-value="id"
                    :label="`Laterality for ${term.label}`"
                    density="compact"
                    variant="outlined"
                    clearable
                    hide-details
                    class="phenotype-item__laterality"
                    @update:model-value="(value) => setModifier(term, value)"
                  />
                </template>
              </v-list-item>
            </v-list>
          </div>
        </v-col>
      </v-row>

      <!-- Additional Curated Phenotypes (Custom / Non-grouped terms) -->
      <div
        v-if="customPhenotypes.length > 0"
        class="mt-4 mb-6"
        data-testid="additional-phenotypes-section"
      >
        <div class="text-h6 mb-2 d-flex align-center text-teal-darken-2">
          <v-icon color="teal-darken-2" class="mr-2">mdi-tag-plus-outline</v-icon>
          Additional Curated Phenotypes
          <v-chip size="x-small" color="teal-darken-2" variant="flat" class="ml-2">
            {{ customPhenotypes.length }}
          </v-chip>
        </div>
        <v-list density="compact" class="mb-2">
          <v-list-item
            v-for="feature in customPhenotypes"
            :key="feature.type?.id"
            class="phenotype-item"
            :data-testid="`custom-phenotype-item-${feature.type?.id}`"
          >
            <template #prepend>
              <v-btn
                :icon="getStateIcon(feature.type?.id)"
                :color="getStateColor(feature.type?.id)"
                variant="text"
                size="small"
                :data-testid="`cycle-custom-${feature.type?.id}`"
                @click="cycleState({ hpo_id: feature.type.id, label: feature.type.label })"
              />
            </template>

            <v-list-item-title>
              {{ feature.type?.label || feature.type?.id }}
              <v-chip
                v-if="feature.onset?.age?.iso8601duration"
                size="x-small"
                color="amber-darken-2"
                variant="outlined"
                class="ml-2"
              >
                {{ feature.onset.age.iso8601duration }}
              </v-chip>
            </v-list-item-title>

            <v-list-item-subtitle class="text-caption">
              {{ feature.type?.id }}
            </v-list-item-subtitle>

            <template #append>
              <div class="d-flex align-center gap-2">
                <v-select
                  v-if="showLaterality(feature.type?.id)"
                  :model-value="getModifierValue(feature.type?.id)"
                  :items="lateralityOptionsFor(feature.type?.id)"
                  item-title="label"
                  item-value="id"
                  :label="`Laterality for ${feature.type?.label || feature.type?.id}`"
                  density="compact"
                  variant="outlined"
                  clearable
                  hide-details
                  class="phenotype-item__laterality mr-2"
                  @update:model-value="
                    (value) =>
                      setModifier({ hpo_id: feature.type.id, label: feature.type.label }, value)
                  "
                />
                <v-btn
                  icon="mdi-close"
                  variant="text"
                  size="small"
                  color="grey"
                  :data-testid="`remove-custom-${feature.type?.id}`"
                  title="Remove phenotype"
                  @click="removeFeature(feature.type?.id)"
                />
              </div>
            </template>
          </v-list-item>
        </v-list>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useGroupedHPO } from '@/composables/useGroupedHPO';
import { useLateralityPolicy } from '@/composables/useLateralityPolicy';
import { apiClient, searchHPOTerms } from '@/api';

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
  // Curation console Task 7 (design spec §3.4): the evidence-code vocabulary,
  // loaded once by the parent's usePhenopacketVocabularies().loadAll() and
  // passed down rather than re-fetched here -- this component never
  // hardcodes an evidence-code value.
  evidenceCodeItems: {
    type: Array,
    default: () => [],
  },
  // Curation console Task 7 (design spec §3.4; curation spec §7): the first
  // listed publication's PMID, formatted `PMID:...`, or null when no
  // publication has been entered yet. A newly-created feature entry
  // attaches `evidence` referencing this; null means omit `evidence`
  // entirely rather than write a reference to nothing.
  anchoringReference: {
    type: String,
    default: null,
  },
});

const emit = defineEmits(['update:modelValue']);

const { groups, loading, fetchGrouped } = useGroupedHPO();
// Curation console Task 7 (design spec §3.4): WHICH HPO term admits WHICH
// laterality modifiers always comes from this live fetch -- never hardcoded
// or special-cased per-term below. `lateralityPolicy.value` is a plain
// object keyed by hpo_id -> array of allowed modifier HPO ids (see
// useLateralityPolicy.js).
const { policy: lateralityPolicy, fetchPolicy: fetchLateralityPolicy } = useLateralityPolicy();

const recommendationFilter = ref('all');
const filterOptions = [
  { title: 'All phenotypes', value: 'all' },
  { title: 'Required only', value: 'required' },
  { title: 'Recommended only', value: 'recommended' },
];

const SYSTEM_COLORS = {
  Kidney: '#1976D2',
  'Urinary tract': '#1976D2',
  'CKD Stages': '#1976D2',
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
  'CKD Stages': 'mdi-format-list-numbered',
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

// Curation console Task 7 (design spec §3.4): the 4 possible laterality
// modifier HPO ids are a small, stable, fixed set (the standard HPO clinical
// modifier subtree) -- NOT one of the six curation vocabularies, and no
// backend endpoint enumerates their labels. Resolved once, live, from
// backend/app/ontology/data/ontology_snapshot.json (2026-07-31):
//   HP:0012832 Bilateral, HP:0012833 Unilateral,
//   HP:0012834 Right,     HP:0012835 Left
// WHICH terms admit WHICH of these four is never decided here -- that always
// comes from `lateralityPolicy` (the live /ontology/laterality-policy
// fetch) above.
const LATERALITY_MODIFIER_LABELS = {
  'HP:0012832': 'Bilateral',
  'HP:0012833': 'Unilateral',
  'HP:0012834': 'Right',
  'HP:0012835': 'Left',
};
const LATERALITY_IDS = new Set(Object.keys(LATERALITY_MODIFIER_LABELS));

// Curation console Task 7 (design spec §3.4, curation spec §7): default
// evidence code attached to features the console creates. Picks the
// evidence-code vocabulary entry labeled "author statement" (ECO:0000033 --
// "Evidence from published author statement", the vocabulary's
// sort_order=1 entry, confirmed live 2026-07-31) when present, falling back
// to the first vocabulary entry so a differently-ordered/labeled vocabulary
// still degrades gracefully. Never a hardcoded ECO id -- always read off
// `props.evidenceCodeItems`, which the parent loads from
// GET /ontology/vocabularies/evidence-code.
const defaultEvidenceCode = computed(() => {
  const items = props.evidenceCodeItems || [];
  const authorStatement = items.find(
    (item) => (item.label || '').trim().toLowerCase() === 'author statement'
  );
  return authorStatement || items[0] || null;
});

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

// Split groups into two columns
// Fixed split at index 5: Left column gets first 5 groups (Brain, Electrolytes, Genital, Urinary tract, Hormones)
// Right column gets remaining groups (CKD Stages, Kidney, Liver, Pancreas, Other)
const groupedByColumns = computed(() => {
  const groupNames = Object.keys(filteredGroups.value);
  const midpoint = 5; // Fixed split point per user requirement

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

// Cycle through states: unknown -> present -> excluded -> unknown.
// Never mutates props.modelValue: `[...arr]` is a shallow copy, so writing
// `copy[i].excluded` would write through to the parent's own object.
const cycleState = (term) => {
  const index = props.modelValue.findIndex((f) => f.type?.id === term.hpo_id);
  const currentState = getState(term.hpo_id);
  const updated = [...props.modelValue];

  if (currentState === 0) {
    const feature = { type: { id: term.hpo_id, label: term.label }, excluded: false };
    // Curation spec §7 / design spec §3.4: attach evidence from the
    // anchoring publication ONLY on a brand-new unknown->present transition
    // (never on present->excluded below, which carries any existing
    // evidence through untouched via the spread) -- and ONLY when a
    // publication has actually been entered and the evidence-code
    // vocabulary has loaded. An evidence entry with no reference is worse
    // than no evidence entry, so both are required or `evidence` is
    // omitted entirely.
    if (props.anchoringReference && defaultEvidenceCode.value) {
      feature.evidence = [
        {
          evidenceCode: {
            id: defaultEvidenceCode.value.id,
            label: defaultEvidenceCode.value.label,
          },
          reference: { id: props.anchoringReference },
        },
      ];
    }
    updated.push(feature);
  } else if (currentState === 1) {
    updated[index] = { ...updated[index], excluded: true };
  } else {
    updated.splice(index, 1);
  }

  emit('update:modelValue', updated);
};

// Whether to show the laterality select for `hpoId`: only for a present
// (not excluded, not unknown) term the live policy admits at least one
// modifier for.
const showLaterality = (hpoId) =>
  getState(hpoId) === 1 && Array.isArray(lateralityPolicy.value[hpoId]);

// The exact set the policy admits for this term, mapped to display labels --
// never assumed to be all four (e.g. HP:0000122 admits Unilateral/Left/Right
// but not Bilateral).
const lateralityOptionsFor = (hpoId) =>
  (lateralityPolicy.value[hpoId] || []).map((id) => ({
    id,
    label: LATERALITY_MODIFIER_LABELS[id] || id,
  }));

const getModifierValue = (hpoId) => {
  const feature = props.modelValue.find((f) => f.type?.id === hpoId);
  const lateralityMod = feature?.modifiers?.find((m) => LATERALITY_IDS.has(m.id));
  return lateralityMod?.id ?? null;
};

// Laterality is mutually exclusive per term (Unilateral vs Left vs Right vs
// Bilateral aren't combinable), so this is a single-select writing
// `modifiers` to either `[]` (cleared) or exactly one `{id,label}`
// ontologyClass -- never a multi-select. Never mutates props.modelValue --
// same immutability discipline as cycleState/selectCKDStage.
// Preserves non-laterality modifiers (e.g. severity).
const setModifier = (term, modifierId) => {
  const index = props.modelValue.findIndex((f) => f.type?.id === term.hpo_id);
  if (index === -1) return;

  const existingModifiers = (props.modelValue[index].modifiers || []).filter(
    (m) => !LATERALITY_IDS.has(m.id)
  );
  const modifiers = modifierId
    ? [
        ...existingModifiers,
        { id: modifierId, label: LATERALITY_MODIFIER_LABELS[modifierId] || modifierId },
      ]
    : existingModifiers;

  const updated = [...props.modelValue];
  updated[index] = { ...updated[index], modifiers };

  emit('update:modelValue', updated);
};

// Get the currently selected CKD stage (only one can be selected at a time)
const getSelectedCKDStage = (ckdStages) => {
  const ckdIds = ckdStages.map((s) => s.hpo_id);
  const selected = props.modelValue.find((f) => ckdIds.includes(f.type?.id) && !f.excluded);
  return selected?.type?.id || null;
};

// Builds a fresh array and a fresh element; safe as written.
// Select a CKD stage (remove all other CKD stages, add the selected one)
const selectCKDStage = (ckdStages, selectedId) => {
  const ckdIds = ckdStages.map((s) => s.hpo_id);
  // Remove all CKD stages from the selection
  let updated = props.modelValue.filter((f) => !ckdIds.includes(f.type?.id));

  // If a stage was selected (not cleared), add it
  if (selectedId) {
    const selectedStage = ckdStages.find((s) => s.hpo_id === selectedId);
    updated.push({
      type: { id: selectedStage.hpo_id, label: selectedStage.label },
      excluded: false,
    });
  }

  emit('update:modelValue', updated);
};

// Quick-Add state (#549)
const quickAddInputRef = ref(null);
const searchQuery = ref('');
const suggestions = ref([]);
const activeIndex = ref(-1);
const quickLaterality = ref(null);
const quickOnset = ref('');

const quickLateralityOptions = [
  { title: 'Bilateral (Alt+B)', value: 'HP:0012832' },
  { title: 'Unilateral (Alt+U)', value: 'HP:0012833' },
  { title: 'Right (Alt+R)', value: 'HP:0012834' },
  { title: 'Left (Alt+L)', value: 'HP:0012835' },
];

const allGroupedHpoIds = computed(() => {
  const ids = new Set();
  const g = groups.value || {};
  for (const groupName of Object.keys(g)) {
    for (const term of g[groupName] || []) {
      const id = term.hpo_id || term.id;
      if (id) ids.add(id);
    }
  }
  return ids;
});

const localTerms = computed(() => {
  const terms = [];
  const seen = new Set();
  const g = groups.value || {};
  for (const groupName of Object.keys(g)) {
    for (const term of g[groupName] || []) {
      const id = term.hpo_id || term.id;
      if (id && !seen.has(id)) {
        seen.add(id);
        terms.push({
          id,
          label: term.label || term.name || '',
          recommendation: term.recommendation,
        });
      }
    }
  }
  return terms;
});

const customPhenotypes = computed(() => {
  return props.modelValue.filter((feature) => {
    const id = feature.type?.id;
    return id && !allGroupedHpoIds.value.has(id);
  });
});

const searchHPO = (q, limit = 10) => {
  if (apiClient?.get) {
    return apiClient.get('/ontology/hpo/autocomplete', { params: { q, limit } });
  }
  if (typeof searchHPOTerms === 'function') {
    return searchHPOTerms(q, limit);
  }
  return Promise.resolve({ data: [] });
};

const isEditableElement = (el) => {
  if (!el) return false;
  const tag = el.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
};

const focusQuickAddInput = () => {
  nextTick(() => {
    if (!quickAddInputRef.value) return;
    if (typeof quickAddInputRef.value.focus === 'function') {
      quickAddInputRef.value.focus();
    } else if (quickAddInputRef.value.$el?.querySelector) {
      const input = quickAddInputRef.value.$el.querySelector('input');
      input?.focus();
    }
  });
};

const handleGlobalKeydown = (event) => {
  const isCmdK = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k';
  const isSlash = event.key === '/' && !event.metaKey && !event.ctrlKey && !event.altKey;

  if (isCmdK || isSlash) {
    if (!isEditableElement(document.activeElement)) {
      event.preventDefault();
      focusQuickAddInput();
    }
  }
};

let currentSearchQuery = '';

const onSearchInput = async (val) => {
  const raw = typeof val === 'string' ? val : searchQuery.value || '';
  if (typeof val === 'string' && searchQuery.value !== val) {
    searchQuery.value = val;
  }
  const q = raw.trim();
  currentSearchQuery = q;
  if (q.length < 2) {
    suggestions.value = [];
    activeIndex.value = -1;
    return;
  }

  const qLower = q.toLowerCase();
  const local = localTerms.value.filter(
    (t) => t.id.toLowerCase().includes(qLower) || t.label.toLowerCase().includes(qLower)
  );
  suggestions.value = local;
  activeIndex.value = local.length > 0 ? 0 : -1;

  try {
    const resp = await searchHPO(q, 10);
    if (currentSearchQuery !== q) return;
    const raw = resp?.data?.data || resp?.data?.terms || resp?.data || [];
    const normalized = (Array.isArray(raw) ? raw : []).map((item) => ({
      id: item.hpo_id || item.id,
      label: item.label || item.name || '',
    }));

    const combined = [...local];
    const seen = new Set(local.map((t) => t.id));
    for (const item of normalized) {
      if (item.id && !seen.has(item.id)) {
        seen.add(item.id);
        combined.push(item);
      }
    }
    suggestions.value = combined;
    if (activeIndex.value === -1 && combined.length > 0) {
      activeIndex.value = 0;
    }
  } catch {
    // Keep local suggestions on network error
  }
};

const handleInputKeydown = (event) => {
  if (event.altKey && !event.ctrlKey && !event.metaKey) {
    const key = event.key.toLowerCase();
    if (key === 'b') {
      event.preventDefault();
      quickLaterality.value = quickLaterality.value === 'HP:0012832' ? null : 'HP:0012832';
      return;
    }
    if (key === 'u') {
      event.preventDefault();
      quickLaterality.value = quickLaterality.value === 'HP:0012833' ? null : 'HP:0012833';
      return;
    }
    if (key === 'r') {
      event.preventDefault();
      quickLaterality.value = quickLaterality.value === 'HP:0012834' ? null : 'HP:0012834';
      return;
    }
    if (key === 'l') {
      event.preventDefault();
      quickLaterality.value = quickLaterality.value === 'HP:0012835' ? null : 'HP:0012835';
      return;
    }
  }

  if (suggestions.value.length === 0) return;

  if (event.key === 'ArrowDown') {
    event.preventDefault();
    activeIndex.value = (activeIndex.value + 1) % suggestions.value.length;
  } else if (event.key === 'ArrowUp') {
    event.preventDefault();
    activeIndex.value =
      (activeIndex.value - 1 + suggestions.value.length) % suggestions.value.length;
  } else if (event.key === 'Enter') {
    event.preventDefault();
    const idx = activeIndex.value >= 0 ? activeIndex.value : 0;
    if (suggestions.value[idx]) {
      addSuggestedTerm(suggestions.value[idx], Boolean(event.shiftKey));
    }
  } else if (event.key === 'Escape') {
    event.preventDefault();
    suggestions.value = [];
    activeIndex.value = -1;
  }
};

const addSuggestedTerm = (term, excluded = false) => {
  if (!term || !term.id) return;

  const hpoId = term.id;
  const label = term.label || term.id;
  const existingIndex = props.modelValue.findIndex((f) => f.type?.id === hpoId);
  const updated = [...props.modelValue];

  let modifiers = [];
  if (!excluded && quickLaterality.value) {
    const policyForTerm = lateralityPolicy.value[hpoId];
    const isAllowed = Array.isArray(policyForTerm)
      ? policyForTerm.includes(quickLaterality.value)
      : Object.keys(lateralityPolicy.value).length === 0;
    if (isAllowed) {
      modifiers.push({
        id: quickLaterality.value,
        label: LATERALITY_MODIFIER_LABELS[quickLaterality.value] || quickLaterality.value,
      });
    }
  }

  let onset = null;
  if (!excluded && quickOnset.value && quickOnset.value.trim()) {
    onset = {
      age: {
        iso8601duration: quickOnset.value.trim(),
      },
    };
  }

  if (existingIndex >= 0) {
    const existing = updated[existingIndex];
    const feature = {
      ...existing,
      excluded,
    };
    if (!excluded) {
      if (modifiers.length > 0) {
        const nonLateralityMods = (existing.modifiers || []).filter(
          (m) => !LATERALITY_IDS.has(m.id)
        );
        feature.modifiers = [...nonLateralityMods, ...modifiers];
      }
      if (onset) {
        feature.onset = onset;
      }
    } else {
      if (feature.modifiers) {
        feature.modifiers = feature.modifiers.filter((m) => !LATERALITY_IDS.has(m.id));
      }
    }
    updated[existingIndex] = feature;
  } else {
    const feature = {
      type: { id: hpoId, label },
      excluded,
    };
    if (!excluded) {
      if (modifiers.length > 0) feature.modifiers = modifiers;
      if (onset) feature.onset = onset;
      if (props.anchoringReference && defaultEvidenceCode.value) {
        feature.evidence = [
          {
            evidenceCode: {
              id: defaultEvidenceCode.value.id,
              label: defaultEvidenceCode.value.label,
            },
            reference: { id: props.anchoringReference },
          },
        ];
      }
    }
    updated.push(feature);
  }

  emit('update:modelValue', updated);

  searchQuery.value = '';
  suggestions.value = [];
  activeIndex.value = -1;
  quickLaterality.value = null;
  quickOnset.value = '';

  focusQuickAddInput();
};

const removeFeature = (hpoId) => {
  const updated = props.modelValue.filter((f) => f.type?.id !== hpoId);
  emit('update:modelValue', updated);
};

onMounted(() => {
  fetchGrouped();
  // Fetched once on mount, alongside the grouped HPO terms (design spec
  // §3.4) -- see the `lateralityPolicy` docs above for why WHICH terms
  // admit WHICH modifiers must always come from this fetch.
  fetchLateralityPolicy();
  window.addEventListener('keydown', handleGlobalKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleGlobalKeydown);
});

defineExpose({
  cycleState,
  addSuggestedTerm,
  searchQuery,
  suggestions,
  activeIndex,
  quickLaterality,
  quickOnset,
  onSearchInput,
  handleInputKeydown,
  handleGlobalKeydown,
  focusQuickAddInput,
  removeFeature,
});
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
.phenotype-item__laterality {
  max-width: 11rem;
}
.quick-add-suggestions-card {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 20;
  max-height: 250px;
  overflow-y: auto;
  margin-top: 4px;
}
.quick-add-suggestion-item {
  cursor: pointer;
}
.quick-add-suggestion-item:hover {
  background-color: rgba(0, 0, 0, 0.04);
}
</style>
