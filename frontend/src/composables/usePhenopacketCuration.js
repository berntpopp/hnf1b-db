import { computed, onScopeDispose, ref } from 'vue';

import {
  appendCurationCorrection,
  appendCurationResolution,
  getCurationLedger,
  previewCurationProjection,
  saveReportObservation,
} from '@/api/domain/curation';
import {
  cloneObservation,
  curationIssues,
  threeWayObservationMerge,
} from '@/utils/curationAdapters';

function stableJson(value) {
  return JSON.stringify(value);
}

export function usePhenopacketCuration(phenopacketId, { previewDelay = 300 } = {}) {
  const ledger = ref(null);
  const observations = ref([]);
  const selectedObservationId = ref(null);
  const draft = ref(null);
  const revision = ref(null);
  const preview = ref(null);
  const loading = ref(false);
  const saving = ref(false);
  const previewing = ref(false);
  const error = ref(null);
  const fieldIssues = ref([]);
  const rebaseConflict = ref(null);
  let baseline = null;
  let previewTimer = null;
  let previewController = null;
  let previewSequence = 0;

  const dirty = computed(
    () => !!draft.value && !!baseline && stableJson(draft.value) !== stableJson(baseline)
  );
  const projection = computed(() =>
    dirty.value ? preview.value?.projection || null : ledger.value?.projection || null
  );
  const conflicts = computed(() => projection.value?.issues || []);

  function cancelPreview() {
    if (previewTimer) clearTimeout(previewTimer);
    previewTimer = null;
    previewController?.abort();
    previewController = null;
    previewSequence += 1;
    previewing.value = false;
  }

  function applyLedgerResponse(response, { preserveDraft = false } = {}) {
    const selected = selectedObservationId.value;
    const localDraft = preserveDraft && draft.value ? cloneObservation(draft.value) : null;
    ledger.value = cloneObservation(response.data);
    observations.value = cloneObservation(response.data.observations || []).sort((a, b) =>
      a.observationId.localeCompare(b.observationId)
    );
    revision.value = response.data.revision;
    const nextId = observations.value.some((item) => item.observationId === selected)
      ? selected
      : observations.value[0]?.observationId || null;
    selectedObservationId.value = nextId;
    const serverObservation =
      observations.value.find((item) => item.observationId === nextId) || null;
    baseline = serverObservation ? cloneObservation(serverObservation) : null;
    draft.value = localDraft || (serverObservation ? cloneObservation(serverObservation) : null);
    preview.value = null;
    fieldIssues.value = [];
  }

  async function load(options = {}) {
    loading.value = true;
    error.value = null;
    try {
      const response = await getCurationLedger(phenopacketId);
      applyLedgerResponse(response, options);
      return response.data;
    } catch (requestError) {
      error.value = requestError;
      throw requestError;
    } finally {
      loading.value = false;
    }
  }

  function selectObservation(observationId, { discard = false } = {}) {
    if (observationId === selectedObservationId.value) return true;
    if (dirty.value && !discard) return false;
    const observation = observations.value.find((item) => item.observationId === observationId);
    if (!observation) return false;
    cancelPreview();
    selectedObservationId.value = observationId;
    baseline = cloneObservation(observation);
    draft.value = cloneObservation(observation);
    preview.value = null;
    fieldIssues.value = [];
    rebaseConflict.value = null;
    return true;
  }

  async function runPreview() {
    if (!draft.value) return;
    previewController?.abort();
    previewController = new AbortController();
    const sequence = ++previewSequence;
    previewing.value = true;
    try {
      const response = await previewCurationProjection(
        phenopacketId,
        cloneObservation(draft.value),
        {
          signal: previewController.signal,
        }
      );
      if (sequence === previewSequence) {
        preview.value = cloneObservation(response.data);
        fieldIssues.value = [];
      }
    } catch (requestError) {
      if (requestError?.name !== 'CanceledError' && requestError?.name !== 'AbortError') {
        if (sequence === previewSequence) {
          preview.value = null;
          fieldIssues.value = curationIssues(requestError);
        }
      }
    } finally {
      if (sequence === previewSequence) previewing.value = false;
    }
  }

  function schedulePreview() {
    if (previewTimer) clearTimeout(previewTimer);
    previewTimer = setTimeout(runPreview, previewDelay);
  }

  function updateDraft(observation) {
    cancelPreview();
    draft.value = cloneObservation(observation);
    preview.value = null;
    fieldIssues.value = [];
    schedulePreview();
  }

  async function save(changeReason) {
    if (!draft.value) return null;
    if (rebaseConflict.value) {
      throw Object.assign(new Error('Resolve the revision comparison before saving.'), {
        code: 'rebase_required',
      });
    }
    cancelPreview();
    saving.value = true;
    error.value = null;
    fieldIssues.value = [];
    try {
      const response = await saveReportObservation(
        phenopacketId,
        cloneObservation(draft.value),
        revision.value,
        changeReason
      );
      applyLedgerResponse(response);
      rebaseConflict.value = null;
      return response.data;
    } catch (requestError) {
      error.value = requestError;
      fieldIssues.value = curationIssues(requestError);
      if (
        requestError?.response?.status === 409 &&
        requestError?.response?.data?.detail?.code === 'revision_mismatch'
      ) {
        const originalBaseline = cloneObservation(baseline);
        const local = cloneObservation(draft.value);
        const response = await getCurationLedger(phenopacketId);
        applyLedgerResponse(response);
        const server = observations.value.find(
          (item) => item.observationId === local.observationId
        );
        draft.value = local;
        const comparison = threeWayObservationMerge(originalBaseline, local, server);
        rebaseConflict.value = {
          observationId: local.observationId,
          base: originalBaseline,
          server: server ? cloneObservation(server) : null,
          local,
          merged: comparison.merged,
          conflicts: comparison.conflicts,
        };
      }
      throw requestError;
    } finally {
      saving.value = false;
    }
  }

  async function resolveConflict(resolution) {
    if (dirty.value) {
      throw Object.assign(new Error('Save the report draft before resolving conflicts.'), {
        code: 'dirty_report',
      });
    }
    saving.value = true;
    try {
      const response = await appendCurationResolution(phenopacketId, resolution, revision.value);
      applyLedgerResponse(response);
      return response.data;
    } finally {
      saving.value = false;
    }
  }

  function applyRebase(decisions = {}) {
    if (!rebaseConflict.value) return false;
    const comparison = threeWayObservationMerge(
      rebaseConflict.value.base,
      rebaseConflict.value.local,
      rebaseConflict.value.server,
      decisions
    );
    rebaseConflict.value = { ...rebaseConflict.value, ...comparison };
    if (comparison.conflicts.length) return false;
    baseline = cloneObservation(rebaseConflict.value.server);
    draft.value = cloneObservation(comparison.merged);
    rebaseConflict.value = null;
    schedulePreview();
    return true;
  }

  function useServerVersion() {
    if (!rebaseConflict.value) return false;
    baseline = cloneObservation(rebaseConflict.value.server);
    draft.value = cloneObservation(rebaseConflict.value.server);
    rebaseConflict.value = null;
    preview.value = null;
    return true;
  }

  async function appendCorrection(correction) {
    if (dirty.value) {
      throw Object.assign(new Error('Save the report draft before appending corrections.'), {
        code: 'dirty_report',
      });
    }
    saving.value = true;
    try {
      const response = await appendCurationCorrection(phenopacketId, correction, revision.value);
      applyLedgerResponse(response);
      return response.data;
    } finally {
      saving.value = false;
    }
  }

  onScopeDispose(() => {
    cancelPreview();
  });

  return {
    ledger,
    observations,
    selectedObservationId,
    draft,
    revision,
    preview,
    projection,
    conflicts,
    dirty,
    loading,
    saving,
    previewing,
    error,
    fieldIssues,
    rebaseConflict,
    load,
    selectObservation,
    updateDraft,
    runPreview,
    save,
    applyRebase,
    useServerVersion,
    resolveConflict,
    appendCorrection,
  };
}
