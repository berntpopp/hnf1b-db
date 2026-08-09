<template>
  <!-- eslint-disable vue/html-self-closing -->
  <fieldset class="phenotype-matrix" :disabled="readonly">
    <legend>Phenotype assessments</legend>
    <p class="text-body-2">Every source question keeps an explicit workflow and clinical state.</p>
    <div class="matrix-tools" :inert="showBulkConfirm ? '' : undefined">
      <label>
        Filter phenotype questions
        <input v-model="filterText" type="search" placeholder="Question or source value" />
      </label>
      <button
        ref="bulkInvoker"
        type="button"
        :disabled="readonly || remainingVisible.length === 0"
        @click="openBulkConfirm"
      >
        Mark visible uncurated as not reported
      </button>
      <button v-if="canUndoBulk" type="button" :disabled="readonly" @click="undoBulk">
        Undo bulk update
      </button>
    </div>
    <div
      v-if="showBulkConfirm"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="bulk-confirm-heading"
      class="bulk-confirm"
      @keydown.esc="closeBulkConfirm"
      @keydown.tab="trapBulkFocus"
    >
      <h3 id="bulk-confirm-heading" class="text-subtitle-1">Confirm scoped bulk update</h3>
      <p>
        Mark {{ remainingVisible.length }} visible uncurated questions as not reported? Questions
        whose source is not applicable are excluded.
      </p>
      <button ref="bulkCancel" type="button" @click="closeBulkConfirm">Cancel</button>
      <button type="button" data-action="confirm-bulk-not-reported" @click="applyBulk">
        Confirm
      </button>
    </div>
    <div
      v-for="assessment in filteredAssessments"
      :key="assessment.assessmentId"
      class="assessment-row"
      :inert="showBulkConfirm ? '' : undefined"
    >
      <div>
        <strong>{{ assessment.column }}</strong>
        <div class="text-caption">Source: {{ assessment.rawValue || '(blank)' }}</div>
      </div>
      <label>
        Mapped finding
        <select
          :data-finding="assessment.assessmentId"
          :value="selectedDefinition(assessment)"
          @change="updateFinding(assessment, $event.target.value)"
        >
          <option value="">Not mapped</option>
          <option
            v-for="definition in definitions(assessment)"
            :key="definition.definitionId"
            :value="definition.definitionId"
          >
            {{ definition.term.label }} ({{ definition.term.id }})
          </option>
        </select>
      </label>
      <label>
        Clinical assessment
        <select
          :data-status="assessment.assessmentId"
          :value="assessment.assessmentStatus || ''"
          @change="updateStatus(assessment, $event.target.value || null)"
        >
          <option value="">Uncurated</option>
          <option
            v-for="state in ASSESSMENT_STATES"
            :key="state.value"
            :value="state.value"
            :disabled="positiveState(state.value) && !canChoosePositive(assessment)"
          >
            {{ state.label }}
          </option>
        </select>
      </label>
      <p v-if="!assessment.findings?.length" class="text-caption">
        Present/absent requires a mapped phenotype finding; retain an explicit non-finding state.
      </p>
      <LateralityEditor
        v-if="hasLaterality(assessment)"
        :assessment-id="assessment.assessmentId"
        :model-value="getLaterality(assessment)"
        @update:model-value="updateLaterality(assessment, $event)"
      />
    </div>
  </fieldset>
</template>

<script setup>
import { computed, nextTick, reactive, ref } from 'vue';

import LateralityEditor from './LateralityEditor.vue';
import { definitionsForColumn } from '@/utils/phenotypeDefinitions';
import {
  ASSESSMENT_STATES,
  getLaterality,
  setAssessmentStatus,
  setLaterality,
} from '@/utils/curationAdapters';

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  readonly: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);
const pendingDefinitions = reactive({});
const filterText = ref('');
const showBulkConfirm = ref(false);
const bulkUndo = ref(null);
const bulkInvoker = ref(null);
const bulkCancel = ref(null);
const LATERALITY_COLUMNS = new Set([
  'Hyperechogenicity',
  'RenalCysts',
  'MulticysticDysplasticKidney',
  'RenalHypoplasia',
  'UrinaryTractMalformation',
]);
const NON_POSITIVE_SOURCE_STATES = new Set(['not_reported', 'not_applicable', 'blank']);
const filteredAssessments = computed(() => {
  const needle = filterText.value.trim().toLowerCase();
  if (!needle) return props.modelValue;
  return props.modelValue.filter((assessment) =>
    `${assessment.column} ${assessment.rawValue || ''}`.toLowerCase().includes(needle)
  );
});
const remainingVisible = computed(() =>
  filteredAssessments.value.filter(
    (assessment) =>
      assessment.curationStatus === 'UNCURATED' && assessment.sourceStatus !== 'not_applicable'
  )
);
const canUndoBulk = computed(() => bulkUndo.value?.after === JSON.stringify(props.modelValue));

function replaceAssessment(assessmentId, next) {
  bulkUndo.value = null;
  emit(
    'update:modelValue',
    props.modelValue.map((item) => (item.assessmentId === assessmentId ? next : item))
  );
}

function updateStatus(assessment, status) {
  let candidate = assessment;
  const available = definitions(assessment);
  if (positiveState(status)) {
    const definitionId = selectedDefinition(assessment) || available[0]?.definitionId;
    const definition = available.find((item) => item.definitionId === definitionId);
    if (definition) candidate = withFinding(assessment, definition);
  }
  if (positiveState(status) && !canChoosePositive(assessment)) return;
  replaceAssessment(assessment.assessmentId, setAssessmentStatus(candidate, status));
}

const positiveState = (status) => ['PRESENT', 'EXCLUDED'].includes(status);
const definitions = (assessment) => definitionsForColumn(assessment.column);
const canChoosePositive = (assessment) =>
  !NON_POSITIVE_SOURCE_STATES.has(assessment.sourceStatus) &&
  (!!selectedDefinition(assessment) || definitions(assessment).length === 1);
const selectedDefinition = (assessment) =>
  Object.prototype.hasOwnProperty.call(pendingDefinitions, assessment.assessmentId)
    ? pendingDefinitions[assessment.assessmentId]
    : assessment.findings?.[0]?.definitionId || '';

function withFinding(assessment, definition) {
  const existing =
    assessment.findings?.find((finding) => finding.definitionId === definition?.definitionId) ||
    assessment.findings?.[0];
  return {
    ...assessment,
    findings: definition
      ? [
          {
            ...(existing || {}),
            definitionId: definition.definitionId,
            term: definition.term,
            sourceTerm: existing?.sourceTerm || null,
            modifiers: LATERALITY_COLUMNS.has(assessment.column) ? existing?.modifiers || [] : [],
          },
        ]
      : [],
  };
}

function updateFinding(assessment, definitionId) {
  bulkUndo.value = null;
  pendingDefinitions[assessment.assessmentId] = definitionId;
  const definition = definitions(assessment).find((item) => item.definitionId === definitionId);
  if (positiveState(assessment.assessmentStatus)) {
    replaceAssessment(assessment.assessmentId, withFinding(assessment, definition));
  }
}

function updateLaterality(assessment, laterality) {
  replaceAssessment(assessment.assessmentId, setLaterality(assessment, laterality));
}

function hasLaterality(assessment) {
  return (
    LATERALITY_COLUMNS.has(assessment.column) &&
    ['PRESENT', 'EXCLUDED'].includes(assessment.assessmentStatus) &&
    assessment.findings?.length
  );
}

function applyBulk() {
  const ids = new Set(remainingVisible.value.map((assessment) => assessment.assessmentId));
  const updated = props.modelValue.map((assessment) =>
    ids.has(assessment.assessmentId) ? setAssessmentStatus(assessment, 'NOT_REPORTED') : assessment
  );
  bulkUndo.value = { before: props.modelValue, after: JSON.stringify(updated) };
  emit('update:modelValue', updated);
  showBulkConfirm.value = false;
  nextTick(() => bulkInvoker.value?.focus());
}

function undoBulk() {
  if (!canUndoBulk.value) return;
  emit('update:modelValue', bulkUndo.value.before);
  bulkUndo.value = null;
}

async function openBulkConfirm() {
  showBulkConfirm.value = true;
  await nextTick();
  bulkCancel.value?.focus();
}

function closeBulkConfirm() {
  showBulkConfirm.value = false;
  nextTick(() => bulkInvoker.value?.focus());
}

function trapBulkFocus(event) {
  const controls = [...(event.currentTarget?.querySelectorAll('button') || [])];
  if (!controls.length) return;
  const first = controls[0];
  const last = controls.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
</script>

<style scoped>
.phenotype-matrix {
  margin: 0;
  padding: 16px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 6px;
}

.phenotype-matrix legend {
  padding: 0 6px;
  font-weight: 700;
}

.assessment-row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(180px, 1fr) minmax(180px, 1fr);
  gap: 12px;
  align-items: end;
  padding: 12px 0;
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.assessment-row label {
  display: grid;
  gap: 4px;
}

.matrix-tools,
.matrix-tools label,
.bulk-confirm {
  display: grid;
  gap: 8px;
}

.matrix-tools {
  grid-template-columns: minmax(220px, 1fr) auto auto;
  align-items: end;
  margin-bottom: 12px;
}

.bulk-confirm {
  padding: 12px;
  border: 1px solid rgb(var(--v-theme-warning));
  border-radius: 4px;
}

select,
input,
button {
  min-height: 44px;
  padding: 8px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
  color: inherit;
}

@media (max-width: 700px) {
  .assessment-row {
    grid-template-columns: 1fr;
  }
}
</style>
