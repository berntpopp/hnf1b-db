import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { getLedger, previewProjection, saveObservation, appendResolution } = vi.hoisted(() => ({
  getLedger: vi.fn(),
  previewProjection: vi.fn(),
  saveObservation: vi.fn(),
  appendResolution: vi.fn(),
}));

vi.mock('@/api/domain/curation', () => ({
  getCurationLedger: getLedger,
  previewCurationProjection: previewProjection,
  saveReportObservation: saveObservation,
  appendCurationResolution: appendResolution,
  appendCurationCorrection: vi.fn(),
}));
import ReportObservationWorkspace from '@/components/curation/reports/ReportObservationWorkspace.vue';

const report = (id, reportId, pmid) => ({
  observationId: id,
  origin: 'manual',
  source: {
    provider: 'fixture',
    datasetId: 'registry',
    sheet: 'Individuals',
    manifestSha256: 'sha256:fixture',
  },
  identifiers: { individualId: '317', sourceSubjectId: '317', reportId },
  publication: { pmid },
  phenotypes: [],
});
const ledger = {
  phenopacketId: 'PP-317',
  revision: 7,
  observations: [report('report-1', 'RPT-1', '123'), report('report-2', 'RPT-2', '456')],
  corrections: [],
  resolutions: [],
  projection: {
    phenopacket: { subject: { id: '317' }, phenotypicFeatures: [], interpretations: [] },
    outputDigest: 'sha256:output',
    issues: [],
  },
};

const mountWorkspace = (options = {}) =>
  mount(ReportObservationWorkspace, {
    ...options,
    global: {
      ...options.global,
      stubs: {
        ...options.global?.stubs,
        RouterLink: RouterLinkStub,
      },
    },
  });

describe('ReportObservationWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getLedger.mockResolvedValue({ data: ledger, headers: { etag: '"7"' } });
    previewProjection.mockResolvedValue({ data: { revision: 7, projection: ledger.projection } });
    saveObservation.mockResolvedValue({
      data: { ...ledger, revision: 8 },
      headers: { etag: '"8"' },
    });
  });

  it('loads one individual ledger and saves only the selected report draft', async () => {
    const wrapper = mountWorkspace({
      props: { phenopacketId: 'PP-317', recordState: 'draft' },
    });
    await flushPromises();
    await wrapper.get('[name="pmid"]').setValue('999');
    await wrapper.get('[name="change-reason"]').setValue('Reviewed report publication identity.');
    await wrapper.get('[data-action="save-report"]').trigger('click');
    await flushPromises();

    expect(saveObservation).toHaveBeenCalledWith(
      'PP-317',
      expect.objectContaining({ observationId: 'report-1', publication: { pmid: '999' } }),
      7,
      'Reviewed report publication identity.'
    );
    expect(wrapper.emitted('dirty-change').at(-1)).toEqual([false]);
  });

  it('uses an accessible discard dialog instead of silently switching a dirty report', async () => {
    const wrapper = mountWorkspace({
      attachTo: document.body,
      props: { phenopacketId: 'PP-317' },
    });
    await flushPromises();
    await wrapper.get('[name="pmid"]').setValue('999');
    await wrapper.findAll('nav button')[1].trigger('click');

    expect(wrapper.get('[role="dialog"]').text()).toContain('Unsaved report changes');
    expect(wrapper.get('[role="dialog"]').element.contains(document.activeElement)).toBe(true);
    expect(wrapper.get('.ledger-workspace__grid').attributes('inert')).toBeDefined();
    await wrapper.get('[role="dialog"]').trigger('keydown', { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(wrapper.get('[data-action="discard-switch"]').element);
    expect(wrapper.text()).toContain('Report RPT-1');
    await wrapper.get('[data-action="discard-switch"]').trigger('click');
    expect(wrapper.text()).toContain('Report RPT-2');
    wrapper.unmount();
  });

  it('routes publication to the exact-revision review workspace', async () => {
    const wrapper = mountWorkspace({
      props: { phenopacketId: 'PP-317', recordState: 'approved' },
    });
    await flushPromises();

    expect(wrapper.find('[data-action="publish-projection"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('Publication requires the exact approved revision');
    const reviewLink = wrapper.getComponent(RouterLinkStub);
    expect(reviewLink.props('to')).toEqual({
      name: 'PhenopacketReview',
      params: { phenopacket_id: 'PP-317' },
    });
    expect(reviewLink.text()).toContain('Open review workspace');
    expect(Object.keys(wrapper.vm.$options.props)).not.toContain('userRole');
    expect(wrapper.vm.$options.emits).not.toContain('published');
  });

  it('makes report editing read-only for in-review and approved revisions', async () => {
    const wrapper = mountWorkspace({
      props: { phenopacketId: 'PP-317', recordState: 'in_review' },
    });
    await flushPromises();

    expect(wrapper.get('fieldset').attributes('disabled')).toBeDefined();
    expect(wrapper.get('[data-action="save-report"]').attributes('disabled')).toBeDefined();
  });

  it.each(['published', 'changes_requested'])(
    'allows backend-supported %s edits',
    async (state) => {
      const wrapper = mountWorkspace({
        props: { phenopacketId: 'PP-317', recordState: state },
      });
      await flushPromises();
      expect(wrapper.get('fieldset').attributes('disabled')).toBeUndefined();
    }
  );

  it('focuses validation summary and links an issue back to its exact control', async () => {
    saveObservation.mockRejectedValueOnce({
      response: {
        status: 422,
        data: {
          detail: {
            code: 'invalid_observation',
            errors: [
              {
                code: 'invalid',
                path: ['observationsById', 'report-1', 'publication', 'pmid'],
                message: 'Invalid PMID',
              },
            ],
          },
        },
      },
    });
    const wrapper = mountWorkspace({
      attachTo: document.body,
      props: { phenopacketId: 'PP-317', recordState: 'draft' },
    });
    await flushPromises();
    await wrapper.get('[name="pmid"]').setValue('invalid');
    await wrapper.get('[name="change-reason"]').setValue('Reviewed publication identity.');
    await wrapper.get('[data-action="save-report"]').trigger('click');
    await flushPromises();
    expect(document.activeElement).toBe(wrapper.get('.validation-errors').element);
    await wrapper.get('.validation-errors button').trigger('click');
    expect(document.activeElement).toBe(wrapper.get('[name="pmid"]').element);
    wrapper.unmount();
  });

  it('blocks a blind retry and requires an explicit field choice after revision mismatch', async () => {
    const latest = {
      ...ledger,
      revision: 8,
      observations: [report('report-1', 'RPT-1', '777'), report('report-2', 'RPT-2', '456')],
    };
    getLedger
      .mockResolvedValueOnce({ data: ledger, headers: { etag: '"7"' } })
      .mockResolvedValueOnce({ data: latest, headers: { etag: '"8"' } });
    saveObservation.mockRejectedValueOnce({
      response: { status: 409, data: { detail: { code: 'revision_mismatch' } } },
    });
    const wrapper = mountWorkspace({
      props: { phenopacketId: 'PP-317', recordState: 'draft' },
    });
    await flushPromises();
    await wrapper.get('[name="pmid"]').setValue('999');
    await wrapper.get('[name="change-reason"]').setValue('Reviewed publication identity.');
    await wrapper.get('[data-action="save-report"]').trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('publication.pmid');
    expect(wrapper.get('[data-action="save-report"]').attributes('disabled')).toBeDefined();
    await wrapper.get('input[type="radio"][value="local"]').setValue();
    await wrapper.get('[data-action="apply-rebase"]').trigger('click');

    expect(wrapper.find('[data-action="apply-rebase"]').exists()).toBe(false);
    expect(wrapper.get('[name="pmid"]').element.value).toBe('999');
    expect(saveObservation).toHaveBeenCalledTimes(1);
  });

  it('emits unavailable for a legacy packet without replacing the legacy form', async () => {
    getLedger.mockRejectedValue({
      response: { status: 422, data: { detail: { code: 'curation_not_available' } } },
    });
    const wrapper = mountWorkspace({ props: { phenopacketId: 'PP-legacy' } });
    await flushPromises();
    expect(wrapper.emitted('unavailable')).toEqual([[]]);
  });
});
