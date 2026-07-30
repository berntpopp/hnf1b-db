<!-- src/components/curation/ClassificationSection.vue -->
<!--
  Classification section content for the curation console (curation console
  design spec §3.3; plan Task 6). Renders inside PhenopacketCreateEdit.vue's
  <CurationSection id="classification">, which already provides the section
  chrome (title, completeness badge, collapse) -- this component owns no
  card of its own, matching VariantAnnotationForm.vue's convention.

  Operates on the SAME primary variant (`interpretations[0]`) Task 5's
  VariantAnnotationForm edits -- the ACMG verdict and criteria live on that
  interpretation's first genomicInterpretation -- plus the three case-level
  `hnf1bCuration.classification*` fields, which have no dependency on a
  variant existing at all.

  ── THE non-negotiable (ADR 0003 D1, read it before touching this file) ───
  `VariantInterpretation` has exactly three fields: `variationDescriptor`,
  `therapeuticActionability`, and the GA4GH-conformant
  `acmgPathogenicityClassification`. This console deliberately writes ONLY
  `genomicInterpretations[0].interpretationStatus` for the verdict --
  `sql_fragments/paths.py:22`'s P/LP filter reads that field, not the
  conformant one, and writing the conformant field too (or instead) would
  silently break that filter for any record this console touches. Every
  mutator below goes through `updateGenomicInterpretation`, which only ever
  replaces `interpretationStatus` or `variantInterpretation.extensions` --
  never adds a key to `variantInterpretation` itself.
-->
<template>
  <div class="classification-section">
    <v-alert v-if="!hasVariant" type="info" variant="tonal" density="compact" class="mb-4">
      Add a variant in the Variant section first to record an ACMG verdict and criteria.
    </v-alert>

    <v-select
      :model-value="verdict"
      :items="interpretationStatusItems"
      item-title="label"
      item-value="value"
      label="ACMG verdict"
      hint="Stored on genomicInterpretations[0].interpretationStatus -- deliberately NOT acmgPathogenicityClassification (ADR 0003 D1)."
      persistent-hint
      :loading="vocabulariesLoading"
      :disabled="vocabulariesLoading || !hasVariant"
      clearable
      class="mb-4"
      @update:model-value="onVerdictChange"
    />

    <div class="text-subtitle-2 text-medium-emphasis mb-2">Criteria</div>

    <v-select
      v-model="pickerCodes"
      :items="acmgCriteriaItems"
      item-title="title"
      item-value="code"
      label="Add ACMG criteria"
      hint="Convenience picker -- writes into the free-text field below, which is what's actually saved."
      persistent-hint
      multiple
      chips
      closable-chips
      :disabled="!hasVariant"
      class="mb-2"
      @update:model-value="onPickerCodesChange"
    />

    <div v-if="pickerCodes.length > 0" class="classification-section__strengths mb-4">
      <div
        v-for="code in pickerCodes"
        :key="code"
        class="classification-section__strength-row d-flex align-center ga-2 mb-1"
      >
        <span class="classification-section__strength-code text-body-2">{{ code }}</span>
        <v-select
          :model-value="pickerStrengths[code]"
          :items="ACMG_STRENGTHS"
          :aria-label="`Strength for ${code}`"
          density="compact"
          hide-details
          class="classification-section__strength-select"
          @update:model-value="(value) => onPickerStrengthChange(code, value)"
        />
      </div>
    </div>

    <v-textarea
      v-model="criteriaText"
      label="Classification criteria (free text)"
      hint="e.g. PM1_Moderate, PM2_Supporting, PP2_Supporting -- editable directly; the picker above is a convenience, this field is the actual write path."
      persistent-hint
      rows="2"
      auto-grow
      :disabled="!hasVariant"
      class="mb-4"
    />

    <v-row>
      <v-col cols="12" md="6">
        <v-select
          :model-value="classificationSystem"
          :items="classificationSystemItems"
          item-title="label"
          item-value="value"
          label="Classification system"
          :loading="vocabulariesLoading"
          :disabled="vocabulariesLoading"
          clearable
          @update:model-value="onClassificationSystemChange"
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-text-field
          :model-value="classificationDate"
          type="date"
          label="Classification date"
          @update:model-value="(value) => $emit('update:classificationDate', value)"
        />
      </v-col>
    </v-row>

    <v-textarea
      :model-value="classificationComment"
      label="Classification comment"
      rows="2"
      auto-grow
      @update:model-value="(value) => $emit('update:classificationComment', value)"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { ACMG_CRITERIA, buildClassificationCriteriaString } from '@/utils/acmgCriteria';

const props = defineProps({
  // The whole `interpretations` array (v-model default) -- only index 0, the
  // primary/first variant, is read or written here, matching the same
  // convention Task 5's CURATION_FIELDS entries and firstVariationDescriptor
  // use.
  modelValue: { type: Array, default: () => [] },
  // Case-level (design spec §3.3): one classification system/date/comment
  // per case, not per variant -- lives on phenopacket.hnf1bCuration, so it
  // is wired through props/emit rather than through `modelValue`, matching
  // VariantAnnotationForm.vue's detectionMethod convention.
  classificationSystem: { type: String, default: null },
  classificationDate: { type: String, default: null },
  classificationComment: { type: String, default: null },
  interpretationStatusItems: { type: Array, default: () => [] },
  classificationSystemItems: { type: Array, default: () => [] },
  vocabulariesLoading: { type: Boolean, default: false },
});

const emit = defineEmits([
  'update:modelValue',
  'update:classificationSystem',
  'update:classificationDate',
  'update:classificationComment',
]);

const ACMG_STRENGTHS = ['VeryStrong', 'Strong', 'Moderate', 'Supporting'];

// Reasonable per-direction default strength for the picker -- a UI
// convenience only, curator-adjustable via the per-code strength select
// below. Not itself part of the corpus's stored string format.
const ACMG_DEFAULT_STRENGTH = {
  PVS1: 'VeryStrong',
  PS1: 'Strong',
  PS2: 'Strong',
  PS3: 'Strong',
  PS4: 'Strong',
  PM1: 'Moderate',
  PM2: 'Moderate',
  PM3: 'Moderate',
  PM4: 'Moderate',
  PM5: 'Moderate',
  PM6: 'Moderate',
  PP1: 'Supporting',
  PP2: 'Supporting',
  PP3: 'Supporting',
  PP4: 'Supporting',
  PP5: 'Supporting',
  BA1: 'VeryStrong',
  BS1: 'Strong',
  BS2: 'Strong',
  BS3: 'Strong',
  BS4: 'Strong',
  BP1: 'Supporting',
  BP2: 'Supporting',
  BP3: 'Supporting',
  BP4: 'Supporting',
  BP5: 'Supporting',
  BP6: 'Supporting',
  BP7: 'Supporting',
};

// `guidelines` (this extension's own field) is a DISPLAY string ("ACMG" /
// "ClinGen CNV"), deliberately different from `hnf1bCuration
// .classificationSystem`'s lowercase vocabulary tokens (`acmg` /
// `clingen_cnv`) confirmed from the sheet. Both fields exist and both
// matter -- see the module doc and design spec §3.3.
const CLASSIFICATION_SYSTEM_TO_GUIDELINES = { acmg: 'ACMG', clingen_cnv: 'ClinGen CNV' };

const acmgCriteriaItems = Object.entries(ACMG_CRITERIA).map(([code, label]) => ({
  code,
  title: `${code} — ${label}`,
}));

const hasVariant = computed(() => (props.modelValue || []).length > 0);

const genomicInterpretation = computed(
  () => props.modelValue?.[0]?.diagnosis?.genomicInterpretations?.[0]
);

const verdict = computed(() => genomicInterpretation.value?.interpretationStatus ?? null);

const classificationCriteriaExtension = computed(() =>
  genomicInterpretation.value?.variantInterpretation?.extensions?.find(
    (e) => e.name === 'classification_criteria'
  )
);

const criteriaText = computed({
  get: () => classificationCriteriaExtension.value?.value?.criteria ?? '',
  set: (value) => setClassificationCriteriaValue({ criteria: value }),
});

/**
 * Emit an updated interpretations array with `mutator` applied to
 * genomicInterpretations[0] only -- every other field (id, progressStatus,
 * other genomicInterpretations entries, other interpretations, and every
 * key on `variantInterpretation`/`variationDescriptor` this section doesn't
 * own) is carried through untouched by the object spreads below.
 */
function updateGenomicInterpretation(mutator) {
  const interpretations = props.modelValue || [];
  const target = interpretations[0];
  if (!target) return;
  const genomicInterpretations = target.diagnosis?.genomicInterpretations || [];
  if (genomicInterpretations.length === 0) return;

  const updatedGI = mutator(genomicInterpretations[0]);
  const updatedInterpretation = {
    ...target,
    diagnosis: {
      ...target.diagnosis,
      genomicInterpretations: [updatedGI, ...genomicInterpretations.slice(1)],
    },
  };

  const next = [...interpretations];
  next[0] = updatedInterpretation;
  emit('update:modelValue', next);
}

/**
 * ADR 0003 D1: the ACMG verdict is deliberately written to
 * `interpretationStatus`, a SIBLING of `variantInterpretation` on the
 * genomicInterpretation -- NEVER to
 * `variantInterpretation.acmgPathogenicityClassification`. This mutator only
 * ever sets `interpretationStatus`; `variantInterpretation` is carried
 * through by the spread in `updateGenomicInterpretation` untouched, so this
 * control can never introduce that key.
 */
function onVerdictChange(value) {
  updateGenomicInterpretation((gi) => ({ ...gi, interpretationStatus: value }));
}

/** Merge `partial` into the existing classification_criteria extension value (or create it), preserving the other key (criteria/guidelines). */
function setClassificationCriteriaValue(partial) {
  updateGenomicInterpretation((gi) => {
    const variantInterpretation = gi.variantInterpretation || {};
    const existingExtension = (variantInterpretation.extensions || []).find(
      (e) => e.name === 'classification_criteria'
    );
    const nextValue = { ...(existingExtension?.value || {}), ...partial };
    const otherExtensions = (variantInterpretation.extensions || []).filter(
      (e) => e.name !== 'classification_criteria'
    );
    return {
      ...gi,
      variantInterpretation: {
        ...variantInterpretation,
        extensions: [...otherExtensions, { name: 'classification_criteria', value: nextValue }],
      },
    };
  });
}

// ── Criteria picker: local state, independent of criteriaText ──────────────
// Deliberately NOT derived reactively from criteriaText on every keystroke --
// seeded once per loaded variant (the watch below) and written TO
// criteriaText only in direct response to an explicit picker interaction
// (onPickerCodesChange/onPickerStrengthChange). This is what keeps a
// hand-edit of the free-text field stable: nothing re-derives or rewrites it
// just because the component re-rendered with the same underlying variant.
const pickerCodes = ref([]);
const pickerStrengths = ref({});

function seedPickerFromText(text) {
  const parsed = (text || '')
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
    .map((tok) => {
      const us = tok.indexOf('_');
      return us === -1
        ? { code: tok, strength: '' }
        : { code: tok.slice(0, us), strength: tok.slice(us + 1) };
    })
    .filter((e) => Object.prototype.hasOwnProperty.call(ACMG_CRITERIA, e.code));

  pickerCodes.value = parsed.map((e) => e.code);
  const strengths = {};
  parsed.forEach((e) => {
    strengths[e.code] = e.strength || ACMG_DEFAULT_STRENGTH[e.code] || 'Supporting';
  });
  pickerStrengths.value = strengths;
}

// Seeds once whenever the identity of the current primary variant changes
// (e.g. loading a record for edit, or a curator adding the first variant) --
// NOT on every criteriaText change, which would fight a hand-edit.
watch(
  () => genomicInterpretation.value?.variantInterpretation?.variationDescriptor?.id,
  () => seedPickerFromText(criteriaText.value),
  { immediate: true }
);

function writeCriteriaFromPicker() {
  const entries = pickerCodes.value.map((code) => ({
    code,
    strength: pickerStrengths.value[code],
  }));
  criteriaText.value = buildClassificationCriteriaString(entries);
}

function onPickerCodesChange(newCodes) {
  const nextStrengths = {};
  newCodes.forEach((code) => {
    nextStrengths[code] =
      pickerStrengths.value[code] || ACMG_DEFAULT_STRENGTH[code] || 'Supporting';
  });
  pickerCodes.value = newCodes;
  pickerStrengths.value = nextStrengths;
  writeCriteriaFromPicker();
}

function onPickerStrengthChange(code, strength) {
  pickerStrengths.value = { ...pickerStrengths.value, [code]: strength };
  writeCriteriaFromPicker();
}

/**
 * design spec §3.3 / plan Task 6: keep the classification_criteria
 * extension's `guidelines` string in sync with the curator's System
 * selection so `parseClassificationCriteria` (used elsewhere to render
 * existing/legacy criteria) keeps working on records this console creates.
 */
function onClassificationSystemChange(value) {
  emit('update:classificationSystem', value);
  if (hasVariant.value) {
    const guidelines = CLASSIFICATION_SYSTEM_TO_GUIDELINES[value];
    if (guidelines) {
      setClassificationCriteriaValue({ guidelines });
    }
  }
}
</script>

<style scoped>
.classification-section__strength-code {
  min-width: 3.5em;
}

.classification-section__strength-select {
  max-width: 12rem;
  flex: 1 1 auto;
}
</style>
