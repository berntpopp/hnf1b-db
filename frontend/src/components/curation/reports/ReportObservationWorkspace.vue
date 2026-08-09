<template>
  <!-- eslint-disable vue/html-self-closing, vue/html-closing-bracket-newline -->
  <section ref="workspaceRoot" aria-labelledby="ledger-heading" class="ledger-workspace">
    <header class="ledger-workspace__header" :inert="pendingObservationId ? '' : undefined">
      <div>
        <h2 id="ledger-heading" class="text-h4">Report observation ledger</h2>
        <p>
          One individual, {{ curation.observations.value.length }} source reports ·
          {{ overallCompleteness.filled }}/{{ overallCompleteness.total }} phenotype assessments
          curated
        </p>
      </div>
      <div class="projection-status" aria-live="polite">
        {{ curation.conflicts.value.length }} unresolved projection conflicts
      </div>
    </header>

    <p v-if="curation.loading.value" role="status">Loading report observations…</p>
    <p v-else-if="!available" role="alert">{{ saveError }}</p>
    <div v-else class="ledger-workspace__grid" :inert="pendingObservationId ? '' : undefined">
      <ReportObservationList
        :observations="curation.observations.value"
        :selected-id="curation.selectedObservationId.value"
        :dirty-id="curation.dirty.value ? curation.selectedObservationId.value : null"
        :issues="curation.conflicts.value"
        :corrections="curation.ledger.value?.corrections || []"
        @select="requestSelection"
      />

      <div class="ledger-workspace__editor">
        <section
          v-if="curation.rebaseConflict.value"
          role="alert"
          aria-labelledby="rebase-heading"
          class="rebase-alert"
        >
          <h2 id="rebase-heading" class="text-h6">Reconcile concurrent report edits</h2>
          <p>
            A newer server revision exists. Saving is blocked until you explicitly reconcile the
            report versions.
          </p>
          <div class="version-comparison">
            <div>
              <h3>Original</h3>
              <pre>{{ pretty(curation.rebaseConflict.value.base) }}</pre>
            </div>
            <div>
              <h3>Your draft</h3>
              <pre>{{ pretty(curation.rebaseConflict.value.local) }}</pre>
            </div>
            <div>
              <h3>Latest server</h3>
              <pre>{{ pretty(curation.rebaseConflict.value.server) }}</pre>
            </div>
          </div>
          <fieldset
            v-for="conflict in curation.rebaseConflict.value.conflicts"
            :key="conflict.path"
            class="merge-choice"
          >
            <legend>
              <code>{{ conflict.path }}</code>
            </legend>
            <label
              ><input v-model="rebaseDecisions[conflict.path]" type="radio" value="local" /> Keep
              your value: <code>{{ pretty(conflict.local) }}</code></label
            >
            <label
              ><input v-model="rebaseDecisions[conflict.path]" type="radio" value="server" /> Keep
              server value: <code>{{ pretty(conflict.server) }}</code></label
            >
          </fieldset>
          <p v-if="rebaseError" role="alert" class="text-error">{{ rebaseError }}</p>
          <button type="button" data-action="apply-rebase" @click="applyRebase">
            Apply reconciled draft
          </button>
          <button type="button" data-action="use-server" @click="useServerVersion">
            Discard draft and use server
          </button>
        </section>
        <ReportObservationEditor
          v-if="curation.draft.value"
          :model-value="curation.draft.value"
          :readonly="!canEdit || !!curation.rebaseConflict.value"
          :correction-readonly="curation.dirty.value"
          :corrections="curation.ledger.value?.corrections || []"
          @update:model-value="curation.updateDraft"
          @append-correction="appendCorrection"
        />

        <section class="save-panel" aria-labelledby="save-report-heading">
          <h2 id="save-report-heading" class="text-h6">Save report draft</h2>
          <label>
            Change reason
            <textarea v-model="changeReason" name="change-reason" rows="2" />
          </label>
          <p v-if="saveError" role="alert" class="text-error">{{ saveError }}</p>
          <button
            type="button"
            data-action="save-report"
            :disabled="
              !canEdit ||
              !curation.dirty.value ||
              curation.saving.value ||
              !!curation.rebaseConflict.value
            "
            @click="saveReport"
          >
            {{ curation.saving.value ? 'Saving…' : 'Save report draft' }}
          </button>
        </section>

        <div
          v-if="curation.fieldIssues.value.length"
          ref="validationSummary"
          role="alert"
          tabindex="-1"
          class="validation-errors"
        >
          <h2 class="text-h6">Report validation issues</h2>
          <ul>
            <li v-for="issue in curation.fieldIssues.value" :key="`${issue.path}-${issue.code}`">
              {{ Array.isArray(issue.path) ? issue.path.join('.') : issue.path }}:
              {{ issue.message }}
              <button type="button" @click="focusIssue(issue)">Focus field</button>
            </li>
          </ul>
        </div>
      </div>

      <aside class="ledger-workspace__projection">
        <CanonicalProjectionPreview
          :projection="curation.projection.value"
          :aria-busy="curation.previewing.value"
        />
        <ConflictResolutionPanel
          :issues="curation.conflicts.value"
          :observations="curation.observations.value"
          :corrections="curation.ledger.value?.corrections || []"
          :readonly="!canEdit || curation.dirty.value"
          @resolve="resolveConflict"
        />
        <section class="publish-panel" aria-labelledby="publish-heading">
          <h2 id="publish-heading" class="text-h6">Publish canonical projection</h2>
          <p v-if="recordState !== 'approved'">Projection must be approved before publication.</p>
          <p v-else-if="userRole !== 'admin'">
            Only an administrator can publish an approved projection.
          </p>
          <label>
            Publication reason
            <textarea v-model="publishReason" rows="2" :disabled="!canPublish" />
          </label>
          <button
            type="button"
            data-action="publish-projection"
            :disabled="!canPublish || !publishReason.trim()"
            @click="publishProjection"
          >
            Publish canonical projection
          </button>
        </section>
      </aside>
    </div>

    <div
      v-if="pendingObservationId"
      role="dialog"
      aria-modal="true"
      aria-labelledby="discard-heading"
      class="dialog-backdrop"
      @keydown.esc="closeDiscardDialog"
      @keydown.tab="trapDialogFocus"
    >
      <div ref="discardDialog" class="dialog-card">
        <h2 id="discard-heading" class="text-h6">Unsaved report changes</h2>
        <p>Discard the current report draft and open the selected source report?</p>
        <button ref="discardCancelButton" type="button" @click="closeDiscardDialog">
          Keep editing
        </button>
        <button type="button" data-action="discard-switch" @click="discardAndSwitch">
          Discard and switch
        </button>
      </div>
    </div>

    <div class="visually-hidden" aria-live="polite">{{ liveMessage }}</div>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';

import { transitionPhenopacket } from '@/api/domain/phenopackets';
import { usePhenopacketCuration } from '@/composables/usePhenopacketCuration';
import { formatApiError } from '@/utils/apiError';
import { assessmentCompleteness, isCurationUnavailable } from '@/utils/curationAdapters';
import CanonicalProjectionPreview from './CanonicalProjectionPreview.vue';
import ConflictResolutionPanel from './ConflictResolutionPanel.vue';
import ReportObservationEditor from './ReportObservationEditor.vue';
import ReportObservationList from './ReportObservationList.vue';

const props = defineProps({
  phenopacketId: { type: String, required: true },
  recordState: { type: String, default: 'draft' },
  userRole: { type: String, default: 'curator' },
});
const emit = defineEmits(['available', 'unavailable', 'dirty-change', 'published']);
const curation = usePhenopacketCuration(props.phenopacketId);
const available = ref(false);
const changeReason = ref('');
const publishReason = ref('');
const saveError = ref('');
const pendingObservationId = ref(null);
const liveMessage = ref('');
const rebaseDecisions = ref({});
const rebaseError = ref('');
const discardCancelButton = ref(null);
const discardDialog = ref(null);
const discardInvoker = ref(null);
const workspaceRoot = ref(null);
const validationSummary = ref(null);

const canEdit = computed(() =>
  ['draft', 'published', 'changes_requested'].includes(props.recordState)
);

const canPublish = computed(
  () =>
    props.recordState === 'approved' &&
    props.userRole === 'admin' &&
    available.value &&
    !!curation.revision.value &&
    !!curation.projection.value &&
    !curation.dirty.value &&
    curation.conflicts.value.length === 0
);
const overallCompleteness = computed(() =>
  assessmentCompleteness(
    curation.observations.value.flatMap((observation) => observation.phenotypes || [])
  )
);

watch(curation.dirty, (value) => emit('dirty-change', value), { immediate: true });
watch(
  pendingObservationId,
  (value) => {
    if (!value) return;
    discardCancelButton.value?.focus();
  },
  { flush: 'post' }
);

onMounted(async () => {
  try {
    await curation.load();
    available.value = true;
    emit('available');
  } catch (error) {
    if (isCurationUnavailable(error)) {
      emit('unavailable');
      return;
    }
    saveError.value = formatApiError(error, 'Failed to load report observations');
  }
});

function requestSelection(observationId) {
  if (!curation.selectObservation(observationId)) {
    discardInvoker.value = document.activeElement;
    pendingObservationId.value = observationId;
  }
}

function closeDiscardDialog() {
  pendingObservationId.value = null;
  requestAnimationFrame(() => discardInvoker.value?.focus());
}

function trapDialogFocus(event) {
  const controls = [...(discardDialog.value?.querySelectorAll('button') || [])];
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

function discardAndSwitch() {
  curation.selectObservation(pendingObservationId.value, { discard: true });
  pendingObservationId.value = null;
  liveMessage.value = 'Opened the selected report and discarded the prior local draft.';
}

async function saveReport() {
  if (changeReason.value.trim().length < 5) {
    saveError.value = 'A change reason of at least 5 characters is required.';
    return;
  }
  saveError.value = '';
  try {
    await curation.save(changeReason.value.trim());
    changeReason.value = '';
    liveMessage.value = 'Report draft saved. The canonical projection preview was refreshed.';
  } catch (error) {
    saveError.value =
      error?.response?.data?.detail?.code === 'revision_mismatch'
        ? 'A newer revision exists. Reconcile the versions above before saving.'
        : formatApiError(error, 'Failed to save report draft');
    if (curation.fieldIssues.value.length) {
      await nextTick();
      validationSummary.value?.focus();
    }
  }
}

function focusIssue(issue) {
  const path = Array.isArray(issue.path) ? issue.path : `${issue.path || ''}`.split('.');
  let selector = null;
  const phenotypeIndex = path.indexOf('phenotypes');
  if (phenotypeIndex >= 0) {
    const assessment = curation.draft.value?.phenotypes?.[Number(path[phenotypeIndex + 1])];
    if (assessment && path.includes('modifiers')) {
      selector = `[data-laterality="${assessment.assessmentId}"]`;
    } else if (assessment && path.includes('findings')) {
      selector = `[data-finding="${assessment.assessmentId}"]`;
    } else if (assessment) selector = `[data-status="${assessment.assessmentId}"]`;
  }
  const section = ['publication', 'variant', 'classification', 'case', 'ages', 'notes'].find(
    (value) => path.includes(value)
  );
  const field = section ? path[path.indexOf(section) + 1] : path.at(-1);
  if (!selector && section === 'publication' && ['pmid', 'doi'].includes(field)) {
    selector = `[name="${field}"]`;
  }
  if (!selector && section === 'publication' && field === 'sourceKey') {
    selector = '[name="publication-source-key"]';
  }
  if (!selector && section === 'publication' && field === 'publicationType') {
    selector = '[name="publication-type"]';
  }
  if (!selector && section === 'variant') selector = `[name="${field}"]`;
  if (!selector && section === 'classification') selector = `[name="classification-${field}"]`;
  if (!selector && section === 'case') selector = `[name="case-${field}"]`;
  if (!selector && section === 'ages') selector = `[name="age-${field}"]`;
  if (!selector && section === 'notes') selector = '[name="source-note"]';
  if (selector) {
    const target = workspaceRoot.value?.querySelector(selector);
    const fallback =
      section === 'ages' ? workspaceRoot.value?.querySelector(`[name="age-${field}-kind"]`) : null;
    (target || fallback)?.focus();
  }
}

const pretty = (value) => JSON.stringify(value, null, 2);

function applyRebase() {
  if (!curation.applyRebase(rebaseDecisions.value)) {
    rebaseError.value = 'Choose your draft or the server value for every conflicting field.';
    return;
  }
  rebaseError.value = '';
  rebaseDecisions.value = {};
  liveMessage.value = 'Concurrent edits reconciled. Review and save the merged report draft.';
}

function useServerVersion() {
  curation.useServerVersion();
  rebaseError.value = '';
  rebaseDecisions.value = {};
  liveMessage.value = 'Local changes discarded. The latest server report is now open.';
}

async function resolveConflict(resolution) {
  saveError.value = '';
  try {
    await curation.resolveConflict(resolution);
    liveMessage.value = 'Projection conflict resolution appended.';
  } catch (error) {
    saveError.value = formatApiError(error, 'Failed to append conflict resolution');
  }
}

async function appendCorrection(correction) {
  if (curation.dirty.value) {
    saveError.value = 'Save or discard the report draft before appending a correction.';
    return;
  }
  try {
    await curation.appendCorrection(correction);
    liveMessage.value = 'Source correction appended without deleting the prior value.';
  } catch (error) {
    saveError.value = formatApiError(error, 'Failed to append source correction');
  }
}

async function publishProjection() {
  if (!canPublish.value || !publishReason.value.trim()) return;
  try {
    const result = await transitionPhenopacket(
      props.phenopacketId,
      'published',
      publishReason.value.trim(),
      curation.revision.value
    );
    emit('published', result.data);
    liveMessage.value = 'Canonical projection published.';
  } catch (error) {
    saveError.value = formatApiError(error, 'Failed to publish canonical projection');
  }
}
</script>

<style scoped>
.ledger-workspace {
  display: grid;
  gap: 16px;
}

.ledger-workspace :deep(.text-caption) {
  color: rgb(var(--v-theme-on-surface));
}

.ledger-workspace__header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 16px;
}

.projection-status {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(var(--v-theme-warning), 0.14);
}

.ledger-workspace__grid {
  display: grid;
  grid-template-columns: minmax(210px, 0.8fr) minmax(420px, 2fr) minmax(270px, 1fr);
  gap: 16px;
  align-items: start;
}

.ledger-workspace__editor,
.ledger-workspace__projection {
  display: grid;
  gap: 16px;
}

.version-comparison {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.version-comparison pre {
  max-height: 240px;
  overflow: auto;
  padding: 8px;
  white-space: pre-wrap;
  background: rgba(var(--v-theme-on-surface), 0.05);
}

.merge-choice {
  display: grid;
  gap: 8px;
  margin-block: 12px;
}

.save-panel,
.publish-panel,
.validation-errors,
.rebase-alert {
  padding: 16px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 6px;
}

.save-panel label,
.publish-panel label {
  display: grid;
  gap: 4px;
  margin-block: 8px;
}

textarea {
  padding: 8px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
  color: inherit;
}

button {
  min-height: 44px;
  padding: 8px 14px;
}

.dialog-backdrop {
  position: fixed;
  z-index: 1000;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 16px;
  background: rgba(0, 0, 0, 0.56);
}

.dialog-card {
  max-width: 480px;
  padding: 24px;
  border-radius: 8px;
  background: rgb(var(--v-theme-surface));
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 1100px) {
  .ledger-workspace__grid {
    grid-template-columns: 240px 1fr;
  }

  .ledger-workspace__projection {
    grid-column: 1 / -1;
  }
}

@media (max-width: 700px) {
  .ledger-workspace__header {
    display: grid;
  }

  .ledger-workspace__grid {
    grid-template-columns: 1fr;
  }

  .ledger-workspace__projection {
    grid-column: auto;
  }
}
</style>
