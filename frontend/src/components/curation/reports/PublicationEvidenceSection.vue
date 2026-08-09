<template>
  <!-- eslint-disable vue/html-self-closing -->
  <fieldset class="report-fieldset" :disabled="readonly">
    <legend>Publication evidence</legend>
    <dl class="source-values">
      <div>
        <dt>Source publication key</dt>
        <dd>{{ modelValue?.sourceKey?.raw || 'Not reported' }}</dd>
      </div>
      <div>
        <dt>Source publication type</dt>
        <dd>{{ modelValue?.publicationType?.raw || 'Not reported' }}</dd>
      </div>
    </dl>
    <div class="field-grid">
      <label>
        Normalized source key
        <input
          name="publication-source-key"
          :value="modelValue?.sourceKey?.value || ''"
          :disabled="modelValue?.sourceKey?.correctionIds?.length > 0"
          @input="updateObserved('sourceKey', $event.target.value)"
        />
      </label>
      <label>
        Normalized publication type
        <input
          name="publication-type"
          :value="modelValue?.publicationType?.value || ''"
          :disabled="modelValue?.publicationType?.correctionIds?.length > 0"
          @input="updateObserved('publicationType', $event.target.value)"
        />
      </label>
      <label>
        PMID
        <input
          name="pmid"
          :value="modelValue?.pmid || ''"
          inputmode="numeric"
          @input="update('pmid', $event.target.value || null)"
        />
      </label>
      <label>
        DOI
        <input
          name="doi"
          :value="modelValue?.doi || ''"
          @input="update('doi', $event.target.value || null)"
        />
      </label>
    </div>
    <p class="text-caption text-medium-emphasis">
      Raw source values and correction history are retained when references are edited.
    </p>
  </fieldset>
</template>

<script setup>
import { updateObservedValue } from '@/utils/curationAdapters';

const props = defineProps({
  modelValue: { type: Object, default: () => ({}) },
  readonly: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);

function update(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value });
}

function updateObserved(key, value) {
  emit('update:modelValue', {
    ...props.modelValue,
    [key]: updateObservedValue(props.modelValue?.[key], value || null),
  });
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

.source-values,
.field-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.source-values div,
.field-grid label {
  display: grid;
  gap: 4px;
}

.source-values dt {
  font-size: 0.75rem;
  color: rgb(var(--v-theme-on-surface));
}

.source-values dd {
  margin: 0;
}

input {
  min-height: 44px;
  padding: 8px 10px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
  color: inherit;
}
</style>
