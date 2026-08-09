<template>
  <!-- eslint-disable vue/html-self-closing, vue/html-closing-bracket-newline -->
  <fieldset class="report-fieldset" :disabled="readonly">
    <legend>Variant and classification</legend>
    <div class="observed-grid">
      <label v-for="field in variantFields" :key="field.key">
        {{ field.label }}
        <span class="raw-value">Source: {{ observed(field.key)?.raw || 'Not reported' }}</span>
        <input
          :name="field.key"
          :value="displayValue(observed(field.key)?.value)"
          :disabled="observed(field.key)?.correctionIds?.length > 0"
          @input="updateObserved('variant', field.key, $event.target.value)"
        />
      </label>
    </div>
    <dl v-if="modelValue.variant?.normalized" class="normalized-variant">
      <div>
        <dt>GA4GH VRS ID</dt>
        <dd>{{ modelValue.variant.normalized.id }}</dd>
      </div>
      <div>
        <dt>Normalized definition</dt>
        <dd>{{ modelValue.variant.normalized.variation?.text?.definition }}</dd>
      </div>
    </dl>
    <h3 class="text-subtitle-1 mt-4">Classification</h3>
    <div class="observed-grid">
      <label v-for="field in classificationFields" :key="field.key">
        {{ field.label }}
        <span class="raw-value"
          >Source: {{ classification(field.key)?.raw || 'Not reported' }}</span
        >
        <input
          :name="`classification-${field.key}`"
          :value="displayValue(classification(field.key)?.value)"
          :disabled="classification(field.key)?.correctionIds?.length > 0"
          @input="updateObserved('classification', field.key, $event.target.value)"
        />
      </label>
    </div>
  </fieldset>
</template>

<script setup>
import { cloneObservation, updateObservedValue } from '@/utils/curationAdapters';

const props = defineProps({
  modelValue: { type: Object, required: true },
  readonly: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);

const variantFields = [
  { key: 'variantType', label: 'Variant type' },
  { key: 'reported', label: 'Variant reported' },
  { key: 'sourceId', label: 'Source variant ID' },
  { key: 'hg19Info', label: 'hg19 INFO' },
  { key: 'hg19', label: 'hg19' },
  { key: 'hg38Info', label: 'hg38 INFO' },
  { key: 'hg38', label: 'hg38' },
  { key: 'varsome', label: 'Varsome' },
  { key: 'detectionMethod', label: 'Detection method' },
  { key: 'segregation', label: 'Segregation' },
];
const classificationFields = [
  { key: 'verdict', label: 'Verdict' },
  { key: 'criteria', label: 'Criteria' },
  { key: 'comment', label: 'Classification comment' },
  { key: 'system', label: 'Classification system' },
  { key: 'date', label: 'Classification date' },
  { key: 'contribution', label: 'Clinical contribution' },
];

const observed = (key) => props.modelValue.variant?.[key];
const classification = (key) => props.modelValue.classification?.[key];
const displayValue = (value) => (typeof value === 'string' ? value : JSON.stringify(value ?? ''));

function updateObserved(section, key, value) {
  const next = cloneObservation(props.modelValue);
  next[section] = next[section] || {};
  next[section][key] = updateObservedValue(next[section][key], value || null);
  emit('update:modelValue', next);
}
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

.observed-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 12px;
}

label {
  display: grid;
  gap: 4px;
}

.raw-value {
  font-size: 0.75rem;
  color: rgb(var(--v-theme-on-surface));
}

input {
  min-height: 44px;
  padding: 8px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
  color: inherit;
}

.normalized-variant {
  display: grid;
  gap: 6px;
  margin-top: 16px;
}

.normalized-variant div {
  display: grid;
  grid-template-columns: 180px 1fr;
}

.normalized-variant dd {
  margin: 0;
}
</style>
