import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import PhenotypeAssessmentMatrix from '@/components/curation/reports/PhenotypeAssessmentMatrix.vue';

const assessment = {
  assessmentId: 'assessment-1',
  column: 'RenalCysts',
  rawValue: 'unilateral left',
  sourceStatus: 'stated',
  curationStatus: 'CURATED',
  assessmentStatus: 'PRESENT',
  findings: [
    {
      definitionId: 'renal-cyst',
      term: { id: 'HP:0000107', label: 'Renal cyst' },
      modifiers: [
        { id: 'HP:0012833', label: 'Unilateral' },
        { id: 'HP:0012835', label: 'Left' },
      ],
    },
  ],
  evidence: [{ reference: 'DOI:10.1/a', evidenceCode: { id: 'ECO:0006013', label: 'author' } }],
};

describe('PhenotypeAssessmentMatrix', () => {
  it('shows the source raw value and every explicit clinical state', () => {
    const wrapper = mount(PhenotypeAssessmentMatrix, { props: { modelValue: [assessment] } });
    expect(wrapper.text()).toContain('unilateral left');
    for (const label of [
      'Present',
      'Absent',
      'Not reported',
      'Not applicable',
      'Unresolved',
      'Not assessed',
      'Uncurated',
    ]) {
      expect(wrapper.text()).toContain(label);
    }
  });

  it('round-trips unilateral-left as both required modifiers', async () => {
    const wrapper = mount(PhenotypeAssessmentMatrix, { props: { modelValue: [assessment] } });
    await wrapper.get('[data-laterality="assessment-1"]').setValue('unilateral-right');
    const emitted = wrapper.emitted('update:modelValue').at(-1)[0][0];
    expect(emitted.findings[0].modifiers).toEqual([
      { id: 'HP:0012833', label: 'Unilateral' },
      { id: 'HP:0012834', label: 'Right' },
    ]);
    expect(emitted.evidence).toEqual(assessment.evidence);
  });

  it('emits not-reported distinctly and preserves evidence metadata', async () => {
    const wrapper = mount(PhenotypeAssessmentMatrix, { props: { modelValue: [assessment] } });
    await wrapper.get('[data-status="assessment-1"]').setValue('NOT_REPORTED');
    const emitted = wrapper.emitted('update:modelValue').at(-1)[0][0];
    expect(emitted).toMatchObject({
      curationStatus: 'CURATED',
      assessmentStatus: 'NOT_REPORTED',
      findings: [],
      evidence: assessment.evidence,
    });
  });

  it('maps a pinned single finding before curating an untouched question as present', async () => {
    const untouched = {
      ...assessment,
      curationStatus: 'UNCURATED',
      assessmentStatus: null,
      findings: [],
    };
    const wrapper = mount(PhenotypeAssessmentMatrix, { props: { modelValue: [untouched] } });

    await wrapper.get('[data-status="assessment-1"]').setValue('PRESENT');

    expect(wrapper.emitted('update:modelValue').at(-1)[0][0]).toMatchObject({
      curationStatus: 'CURATED',
      assessmentStatus: 'PRESENT',
      findings: [{ definitionId: 'renal-cyst', term: { id: 'HP:0000107' } }],
    });
  });

  it('requires an explicit pinned definition for multi-option CKD questions', async () => {
    const ckd = {
      ...assessment,
      assessmentId: 'ckd',
      column: 'RenalInsufficancy',
      curationStatus: 'UNCURATED',
      assessmentStatus: null,
      findings: [],
    };
    const wrapper = mount(PhenotypeAssessmentMatrix, { props: { modelValue: [ckd] } });
    expect(
      wrapper.get('[data-status="ckd"] option[value="PRESENT"]').attributes('disabled')
    ).toBeDefined();

    await wrapper.get('[data-finding="ckd"]').setValue('ckd-stage-3');
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
    await wrapper.get('[data-status="ckd"]').setValue('PRESENT');

    expect(wrapper.emitted('update:modelValue').at(-1)[0][0].findings).toEqual([
      expect.objectContaining({
        definitionId: 'ckd-stage-3',
        term: { id: 'HP:0012625', label: 'Stage 3 chronic kidney disease' },
      }),
    ]);
  });

  it('preserves source term and compound laterality when toggling assertion polarity', async () => {
    const withSourceTerm = {
      ...assessment,
      findings: [
        {
          ...assessment.findings[0],
          sourceTerm: { id: 'LOCAL:renal-cyst', label: 'source cyst' },
        },
      ],
    };
    const wrapper = mount(PhenotypeAssessmentMatrix, { props: { modelValue: [withSourceTerm] } });
    await wrapper.get('[data-status="assessment-1"]').setValue('EXCLUDED');
    const finding = wrapper.emitted('update:modelValue').at(-1)[0][0].findings[0];
    expect(finding.sourceTerm).toEqual(withSourceTerm.findings[0].sourceTerm);
    expect(finding.modifiers).toEqual(withSourceTerm.findings[0].modifiers);
  });

  it('disables positive states for NA/NR/blank sources and hides forbidden laterality', () => {
    const notReported = {
      ...assessment,
      assessmentId: 'nr',
      sourceStatus: 'not_reported',
      curationStatus: 'UNCURATED',
      assessmentStatus: null,
      findings: [],
    };
    const gout = {
      ...assessment,
      assessmentId: 'gout',
      column: 'Gout',
      findings: [
        { definitionId: 'gout', term: { id: 'HP:0001997', label: 'Gout' }, modifiers: [] },
      ],
    };
    const wrapper = mount(PhenotypeAssessmentMatrix, {
      props: { modelValue: [notReported, gout] },
    });
    expect(
      wrapper.get('[data-status="nr"] option[value="PRESENT"]').attributes('disabled')
    ).toBeDefined();
    expect(wrapper.find('[data-laterality="gout"]').exists()).toBe(false);
  });

  it('confirms and can undo a visible-only mark-not-reported bulk action', async () => {
    const untouched = [
      {
        ...assessment,
        assessmentId: 'one',
        curationStatus: 'UNCURATED',
        assessmentStatus: null,
        findings: [],
      },
      {
        ...assessment,
        assessmentId: 'two',
        column: 'Gout',
        rawValue: 'no',
        curationStatus: 'UNCURATED',
        assessmentStatus: null,
        findings: [],
      },
    ];
    const wrapper = mount(PhenotypeAssessmentMatrix, { props: { modelValue: untouched } });
    await wrapper.get('input[type="search"]').setValue('Gout');
    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('Mark visible'))
      .trigger('click');
    await wrapper.get('[data-action="confirm-bulk-not-reported"]').trigger('click');
    const updated = wrapper.emitted('update:modelValue').at(-1)[0];
    expect(updated[0].assessmentStatus).toBeNull();
    expect(updated[1].assessmentStatus).toBe('NOT_REPORTED');
    await wrapper.setProps({ modelValue: updated });
    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('Undo bulk'))
      .trigger('click');
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual(untouched);
  });
});
