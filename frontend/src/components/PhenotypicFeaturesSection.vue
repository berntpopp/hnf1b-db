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
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useGroupedHPO } from '@/composables/useGroupedHPO';
import { useLateralityPolicy } from '@/composables/useLateralityPolicy';

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
  return feature?.modifiers?.[0]?.id ?? null;
};

// Laterality is mutually exclusive per term (Unilateral vs Left vs Right vs
// Bilateral aren't combinable), so this is a single-select writing
// `modifiers` to either `[]` (cleared) or exactly one `{id,label}`
// ontologyClass -- never a multi-select. Never mutates props.modelValue --
// same immutability discipline as cycleState/selectCKDStage.
const setModifier = (term, modifierId) => {
  const index = props.modelValue.findIndex((f) => f.type?.id === term.hpo_id);
  if (index === -1) return;

  const updated = [...props.modelValue];
  const modifiers = modifierId
    ? [{ id: modifierId, label: LATERALITY_MODIFIER_LABELS[modifierId] || modifierId }]
    : [];
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

onMounted(() => {
  fetchGrouped();
  // Fetched once on mount, alongside the grouped HPO terms (design spec
  // §3.4) -- see the `lateralityPolicy` docs above for why WHICH terms
  // admit WHICH modifiers must always come from this fetch.
  fetchLateralityPolicy();
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
</style>
