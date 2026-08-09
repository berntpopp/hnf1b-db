<template>
  <!-- eslint-disable vue/html-self-closing -->
  <fieldset class="report-fieldset" :disabled="readonly">
    <legend>Source provenance, case, ages, and notes</legend>
    <dl class="source-grid">
      <div>
        <dt>Provider</dt>
        <dd>{{ modelValue.source?.provider }}</dd>
      </div>
      <div>
        <dt>Dataset</dt>
        <dd>{{ modelValue.source?.datasetId }}</dd>
      </div>
      <div>
        <dt>Sheet</dt>
        <dd>{{ modelValue.source?.sheet }}</dd>
      </div>
      <div>
        <dt>Manifest</dt>
        <dd>{{ modelValue.source?.manifestSha256 }}</dd>
      </div>
      <div>
        <dt>Source reviewer</dt>
        <dd>{{ modelValue.sourceReview?.reviewerDisplayLabel || 'Not mapped' }}</dd>
      </div>
      <div>
        <dt>Source review date</dt>
        <dd>{{ modelValue.sourceReview?.reviewedOn || 'Not reported' }}</dd>
      </div>
    </dl>

    <h3 class="text-subtitle-1 mt-4">Case</h3>
    <div class="observed-grid">
      <label v-for="field in caseFields" :key="field.key">
        {{ field.label }}
        <span>Source: {{ modelValue.case?.[field.key]?.raw || 'Not reported' }}</span>
        <input
          :name="`case-${field.key}`"
          :value="displayValue(modelValue.case?.[field.key]?.value)"
          :disabled="modelValue.case?.[field.key]?.correctionIds?.length > 0"
          @input="updateObserved('case', field.key, $event.target.value)"
        />
      </label>
    </div>

    <h3 class="text-subtitle-1 mt-4">Ages</h3>
    <div class="observed-grid">
      <label v-for="field in ageFields" :key="field.key">
        {{ field.label }}
        <span>Source: {{ modelValue.ages?.[field.key]?.raw || 'Not reported' }}</span>
        <span>
          Normalized:
          {{ modelValue.ages?.[field.key]?.value?.iso8601Duration || 'Not projected' }}
        </span>
        Projection type
        <select
          :name="`age-${field.key}-kind`"
          :value="ageKind(field.key)"
          :disabled="!modelValue.ages?.[field.key] || hasCorrections(modelValue.ages?.[field.key])"
          @change="updateAgeKind(field.key, $event.target.value)"
        >
          <option value="age">Age</option>
          <option value="gestationalAge">Gestational age</option>
          <option value="ontologyClass">Ontology class</option>
          <option value="unprojected">Unprojected</option>
        </select>
        <input
          v-if="['age', 'gestationalAge'].includes(ageKind(field.key))"
          :name="`age-${field.key}`"
          :value="modelValue.ages?.[field.key]?.value?.iso8601Duration || ''"
          :disabled="hasCorrections(modelValue.ages?.[field.key])"
          @input="updateAge(field.key, $event.target.value)"
        />
        <template v-else-if="ageKind(field.key) === 'ontologyClass'">
          <input
            :name="`age-${field.key}-term-id`"
            aria-label="Onset ontology identifier"
            :value="ageTerm(field.key).id || ''"
            :disabled="hasCorrections(modelValue.ages?.[field.key])"
            @input="updateAgeTerm(field.key, 'id', $event.target.value)"
          />
          <input
            :name="`age-${field.key}-term-label`"
            aria-label="Onset ontology label"
            :value="ageTerm(field.key).label || ''"
            :disabled="hasCorrections(modelValue.ages?.[field.key])"
            @input="updateAgeTerm(field.key, 'label', $event.target.value)"
          />
        </template>
      </label>
    </div>

    <label class="notes-field">
      Report-level source note
      <span>Source: {{ modelValue.notes?.comment?.raw || 'Not reported' }}</span>
      <textarea
        name="source-note"
        :value="modelValue.notes?.comment?.value || ''"
        :disabled="modelValue.notes?.comment?.correctionIds?.length > 0"
        rows="3"
        @input="updateObserved('notes', 'comment', $event.target.value)"
      />
    </label>
  </fieldset>
</template>

<script setup>
import { reactive } from 'vue';

import { cloneObservation, updateObservedValue } from '@/utils/curationAdapters';

const props = defineProps({
  modelValue: { type: Object, required: true },
  readonly: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);
const pendingAgeKinds = reactive({});
const pendingAgeTerms = reactive({});

const caseFields = [
  { key: 'duplicateCheck', label: 'Duplicate check' },
  { key: 'problematic', label: 'Problematic' },
  { key: 'cohort', label: 'Cohort' },
  { key: 'familyHistory', label: 'Family history' },
];
const ageFields = [
  { key: 'onset', label: 'Age at onset' },
  { key: 'reported', label: 'Age reported' },
];
const displayValue = (value) => (typeof value === 'string' ? value : JSON.stringify(value ?? ''));

function updateObserved(section, key, value) {
  const next = cloneObservation(props.modelValue);
  next[section] = next[section] || {};
  next[section][key] = updateObservedValue(next[section][key], value || null);
  emit('update:modelValue', next);
}

function updateAge(key, iso8601Duration) {
  const next = cloneObservation(props.modelValue);
  const current = next.ages?.[key];
  next.ages = next.ages || {};
  next.ages[key] = updateObservedValue(
    current,
    iso8601Duration ? { kind: ageKind(key), iso8601Duration } : { kind: 'unprojected' }
  );
  emit('update:modelValue', next);
}

function updateAgeKind(key, kind) {
  pendingAgeKinds[pendingKey(key)] = kind;
  const next = cloneObservation(props.modelValue);
  const current = next.ages?.[key];
  if (!current) return;
  let value = null;
  if (kind === 'unprojected') value = { kind };
  if (['age', 'gestationalAge'].includes(kind) && current.value?.iso8601Duration) {
    value = { kind, iso8601Duration: current.value.iso8601Duration };
  }
  if (kind === 'ontologyClass' && current.value?.term?.id && current.value?.term?.label) {
    value = { kind, term: current.value.term };
  }
  if (!value) return;
  next.ages = next.ages || {};
  next.ages[key] = updateObservedValue(current, value);
  emit('update:modelValue', next);
}

function updateAgeTerm(key, field, value) {
  const next = cloneObservation(props.modelValue);
  const current = next.ages?.[key];
  if (!current) return;
  pendingAgeTerms[pendingKey(key)] = { ...ageTerm(key), [field]: value };
  if (!pendingAgeTerms[pendingKey(key)].id || !pendingAgeTerms[pendingKey(key)].label) return;
  next.ages = next.ages || {};
  next.ages[key] = updateObservedValue(current, {
    kind: 'ontologyClass',
    term: pendingAgeTerms[pendingKey(key)],
  });
  emit('update:modelValue', next);
}

const pendingKey = (key) => `${props.modelValue.observationId}:${key}`;
const ageKind = (key) =>
  pendingAgeKinds[pendingKey(key)] || props.modelValue.ages?.[key]?.value?.kind || 'unprojected';
const ageTerm = (key) =>
  pendingAgeTerms[pendingKey(key)] ||
  props.modelValue.ages?.[key]?.value?.term || { id: '', label: '' };

const hasCorrections = (observed) => !!observed?.correctionIds?.length;
</script>

<style scoped>
.report-fieldset {
  margin: 0;
  padding: 16px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 6px;
}

.report-fieldset legend {
  padding: 0 6px;
  font-weight: 700;
}

.source-grid,
.observed-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.source-grid div,
.observed-grid label,
.notes-field {
  display: grid;
  gap: 4px;
}

.source-grid dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.observed-grid span,
.notes-field span {
  font-size: 0.75rem;
  color: rgb(var(--v-theme-on-surface));
}

input,
textarea,
select {
  min-height: 44px;
  padding: 8px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
  color: inherit;
}

.notes-field {
  margin-top: 16px;
}
</style>
