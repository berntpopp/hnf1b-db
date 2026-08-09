<template>
  <section v-if="modelValue" class="report-editor" :aria-labelledby="headingId">
    <header>
      <h2 :id="headingId" class="text-h5">
        Report {{ modelValue.identifiers?.reportId || modelValue.observationId }}
      </h2>
      <p class="text-caption">Observation ID: {{ modelValue.observationId }}</p>
    </header>
    <PublicationEvidenceSection
      :model-value="modelValue.publication || {}"
      :readonly="readonly"
      @update:model-value="updateSection('publication', $event)"
    />
    <SourceProvenanceSection
      :model-value="modelValue"
      :readonly="readonly"
      @update:model-value="$emit('update:modelValue', $event)"
    />
    <VariantObservationEditor
      :model-value="modelValue"
      :readonly="readonly"
      @update:model-value="$emit('update:modelValue', $event)"
    />
    <PhenotypeAssessmentMatrix
      :key="modelValue.observationId"
      :model-value="modelValue.phenotypes || []"
      :readonly="readonly"
      @update:model-value="updateSection('phenotypes', $event)"
    />
    <CorrectionAppendPanel
      :observation="modelValue"
      :corrections="corrections"
      :readonly="readonly || correctionReadonly"
      @append="$emit('appendCorrection', $event)"
    />
  </section>
</template>

<script setup>
import { computed } from 'vue';

import PhenotypeAssessmentMatrix from './PhenotypeAssessmentMatrix.vue';
import CorrectionAppendPanel from './CorrectionAppendPanel.vue';
import PublicationEvidenceSection from './PublicationEvidenceSection.vue';
import SourceProvenanceSection from './SourceProvenanceSection.vue';
import VariantObservationEditor from './VariantObservationEditor.vue';
import { cloneObservation } from '@/utils/curationAdapters';

const props = defineProps({
  modelValue: { type: Object, default: null },
  readonly: { type: Boolean, default: false },
  correctionReadonly: { type: Boolean, default: false },
  corrections: { type: Array, default: () => [] },
});
const emit = defineEmits(['update:modelValue', 'appendCorrection']);
const headingId = computed(() => `report-editor-${props.modelValue?.observationId || 'empty'}`);

function updateSection(section, value) {
  const next = cloneObservation(props.modelValue);
  next[section] = value;
  emit('update:modelValue', next);
}
</script>

<style scoped>
.report-editor {
  display: grid;
  gap: 16px;
}
</style>
