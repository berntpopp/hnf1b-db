import { effectScope } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { getLedger, previewProjection, saveObservation, appendResolution, appendCorrection } =
  vi.hoisted(() => ({
    getLedger: vi.fn(),
    previewProjection: vi.fn(),
    saveObservation: vi.fn(),
    appendResolution: vi.fn(),
    appendCorrection: vi.fn(),
  }));

vi.mock('@/api/domain/curation', () => ({
  getCurationLedger: getLedger,
  previewCurationProjection: previewProjection,
  saveReportObservation: saveObservation,
  appendCurationResolution: appendResolution,
  appendCurationCorrection: appendCorrection,
}));

import { usePhenopacketCuration } from '@/composables/usePhenopacketCuration';

const reports = [
  {
    observationId: 'report-1',
    identifiers: { reportId: 'RPT-1' },
    publication: { pmid: '123', doi: '10.1/a' },
    phenotypes: [],
  },
  {
    observationId: 'report-2',
    identifiers: { reportId: 'RPT-2' },
    publication: { pmid: '456' },
    phenotypes: [],
  },
];

const ledger = (revision = 7, observations = reports) => ({
  phenopacketId: 'PP-317',
  revision,
  observations,
  corrections: [],
  resolutions: [],
  projection: {
    phenopacket: { subject: { id: '317' }, phenotypicFeatures: [], interpretations: [] },
    outputDigest: `sha256:${revision}`,
    issues: [],
  },
});

function createCuration(options = {}) {
  const scope = effectScope();
  const state = scope.run(() => usePhenopacketCuration('PP-317', options));
  return { scope, state };
}

describe('usePhenopacketCuration', () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
    getLedger.mockResolvedValue({ data: ledger(), headers: { etag: '"7"' } });
  });

  it('loads sorted report drafts and edits without mutating the server baseline', async () => {
    const { scope, state } = createCuration();
    await state.load();

    state.updateDraft({ ...state.draft.value, publication: { pmid: '999', doi: '10.1/a' } });

    expect(state.selectedObservationId.value).toBe('report-1');
    expect(state.dirty.value).toBe(true);
    expect(state.draft.value.publication).toEqual({ pmid: '999', doi: '10.1/a' });
    expect(state.observations.value[0].publication).toEqual({ pmid: '123', doi: '10.1/a' });
    expect(state.projection.value).toBeNull();
    scope.stop();
  });

  it('blocks report switching while the selected draft is dirty unless explicitly discarded', async () => {
    const { scope, state } = createCuration();
    await state.load();
    state.updateDraft({ ...state.draft.value, publication: { pmid: '999' } });

    expect(state.selectObservation('report-2')).toBe(false);
    expect(state.selectedObservationId.value).toBe('report-1');
    expect(state.selectObservation('report-2', { discard: true })).toBe(true);
    expect(state.selectedObservationId.value).toBe('report-2');
    expect(state.dirty.value).toBe(false);
    scope.stop();
  });

  it('debounces previews and aborts an obsolete in-flight response', async () => {
    vi.useFakeTimers();
    const requests = [];
    previewProjection.mockImplementation((_id, observation, options) => {
      requests.push({ observation, signal: options.signal });
      return new Promise(() => {});
    });
    const { scope, state } = createCuration({ previewDelay: 10 });
    await state.load();

    state.updateDraft({ ...state.draft.value, publication: { pmid: '111' } });
    await vi.advanceTimersByTimeAsync(10);
    state.updateDraft({ ...state.draft.value, publication: { pmid: '222' } });
    await vi.advanceTimersByTimeAsync(10);

    expect(requests).toHaveLength(2);
    expect(requests[0].signal.aborted).toBe(true);
    expect(requests[1].signal.aborted).toBe(false);
    expect(requests[1].observation.publication.pmid).toBe('222');
    scope.stop();
  });

  it('invalidates an in-flight preview as soon as the draft changes', async () => {
    vi.useFakeTimers();
    let resolveFirst;
    let firstSignal;
    previewProjection.mockImplementationOnce((_id, _observation, options) => {
      firstSignal = options.signal;
      return new Promise((resolve) => {
        resolveFirst = resolve;
      });
    });
    const { scope, state } = createCuration({ previewDelay: 50 });
    await state.load();

    state.updateDraft({ ...state.draft.value, publication: { pmid: '111' } });
    await vi.advanceTimersByTimeAsync(50);
    state.updateDraft({ ...state.draft.value, publication: { pmid: '222' } });

    resolveFirst({ data: { projection: { outputDigest: 'sha256:obsolete' } } });
    await Promise.resolve();

    expect(firstSignal.aborted).toBe(true);
    expect(state.preview.value).toBeNull();
    scope.stop();
  });

  it('saves with the current revision and re-baselines from the server response', async () => {
    saveObservation.mockResolvedValue({ data: ledger(8), headers: { etag: '"8"' } });
    const { scope, state } = createCuration();
    await state.load();
    state.updateDraft({ ...state.draft.value, publication: { pmid: '999' } });

    await state.save('Reviewed all report-level evidence.');

    expect(saveObservation).toHaveBeenCalledWith(
      'PP-317',
      expect.objectContaining({ observationId: 'report-1', publication: { pmid: '999' } }),
      7,
      'Reviewed all report-level evidence.'
    );
    expect(state.revision.value).toBe(8);
    expect(state.dirty.value).toBe(false);
    scope.stop();
  });

  it('retains a local draft and requires an explicit three-way rebase after revision mismatch', async () => {
    saveObservation.mockRejectedValue({
      response: { status: 409, data: { detail: { code: 'revision_mismatch', errors: [] } } },
    });
    getLedger
      .mockResolvedValueOnce({ data: ledger(), headers: { etag: '"7"' } })
      .mockResolvedValueOnce({
        data: ledger(8, [
          { ...reports[0], publication: { pmid: '123', doi: '10.1/server' } },
          reports[1],
        ]),
        headers: { etag: '"8"' },
      });
    const { scope, state } = createCuration();
    await state.load();
    state.updateDraft({ ...state.draft.value, publication: { pmid: '999', doi: '10.1/a' } });

    await expect(state.save('Reviewed all report-level evidence.')).rejects.toBeTruthy();

    expect(state.draft.value.publication.pmid).toBe('999');
    expect(state.rebaseConflict.value).toMatchObject({
      observationId: 'report-1',
      server: { publication: { pmid: '123', doi: '10.1/server' } },
      local: { publication: { pmid: '999', doi: '10.1/a' } },
      conflicts: [],
    });
    expect(state.revision.value).toBe(8);

    await expect(state.save('Blind retry must be blocked.')).rejects.toMatchObject({
      code: 'rebase_required',
    });
    expect(saveObservation).toHaveBeenCalledTimes(1);

    expect(state.applyRebase({})).toBe(true);
    expect(state.draft.value.publication).toEqual({ pmid: '999', doi: '10.1/server' });
    expect(state.dirty.value).toBe(true);
    scope.stop();
  });

  it('does not mislabel or reload for a non-revision 409', async () => {
    saveObservation.mockRejectedValue({
      response: { status: 409, data: { detail: { code: 'invalid_transition', errors: [] } } },
    });
    const { scope, state } = createCuration();
    await state.load();
    state.updateDraft({ ...state.draft.value, publication: { pmid: '999' } });

    await expect(state.save('Reviewed all report-level evidence.')).rejects.toBeTruthy();

    expect(getLedger).toHaveBeenCalledTimes(1);
    expect(state.rebaseConflict.value).toBeNull();
    scope.stop();
  });

  it('never appends a conflict resolution over an unsaved report draft', async () => {
    const { scope, state } = createCuration();
    await state.load();
    state.updateDraft({ ...state.draft.value, publication: { pmid: '999' } });

    await expect(state.resolveConflict({ conflictKey: 'subject:sex' })).rejects.toMatchObject({
      code: 'dirty_report',
    });
    expect(appendResolution).not.toHaveBeenCalled();
    expect(state.draft.value.publication.pmid).toBe('999');
    scope.stop();
  });

  it('appends a digest-bound resolution and applies the returned ledger', async () => {
    appendResolution.mockResolvedValue({ data: ledger(8), headers: { etag: '"8"' } });
    const { scope, state } = createCuration();
    await state.load();

    await state.resolveConflict({
      conflictKey: 'subject:sex',
      candidateSetDigest: 'sha256:current',
      strategy: 'select_observations',
      selectedObservationIds: ['report-1'],
      reason: 'Use the directly observed source report.',
    });

    expect(appendResolution).toHaveBeenCalledWith(
      'PP-317',
      expect.objectContaining({ candidateSetDigest: 'sha256:current' }),
      7
    );
    expect(state.revision.value).toBe(8);
    scope.stop();
  });
});
