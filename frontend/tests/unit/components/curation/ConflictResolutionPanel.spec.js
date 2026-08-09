import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import ConflictResolutionPanel from '@/components/curation/reports/ConflictResolutionPanel.vue';

const issue = {
  conflictKey: 'subject:sex',
  candidateSetDigest: 'sha256:current',
  message: 'Projection conflict: subject:sex',
};
const observations = [
  {
    observationId: 'report-1',
    identifiers: { reportId: 'RPT-1', sex: { raw: 'M', value: 'MALE' } },
    publication: { pmid: '123' },
    sourceReview: { reviewerDisplayLabel: 'Reviewer A', reviewedOn: '2024-01-01' },
  },
  {
    observationId: 'report-2',
    identifiers: { reportId: 'RPT-2', sex: { raw: 'F', value: 'FEMALE' } },
    publication: { doi: '10.1/a' },
    sourceReview: { reviewerDisplayLabel: 'Reviewer B', reviewedOn: '2025-01-01' },
  },
];

describe('ConflictResolutionPanel', () => {
  it('shows evidence side by side and requires a rationale', async () => {
    const wrapper = mount(ConflictResolutionPanel, { props: { issues: [issue], observations } });
    expect(wrapper.text()).toContain('RPT-1');
    expect(wrapper.text()).toContain('Reviewer A');
    expect(wrapper.text()).toContain('MALE');
    expect(wrapper.text()).toContain('RPT-2');
    expect(wrapper.text()).toContain('FEMALE');

    await wrapper.get('[data-candidate="report-1"]').setValue(true);
    await wrapper.get('[data-resolve="subject:sex"]').trigger('click');
    expect(wrapper.emitted('resolve')).toBeUndefined();
    expect(wrapper.text()).toContain('Resolution reason is required');
  });

  it('emits a digest-bound select-observations resolution', async () => {
    const wrapper = mount(ConflictResolutionPanel, { props: { issues: [issue], observations } });
    await wrapper.get('[data-candidate="report-1"]').setValue(true);
    await wrapper
      .get('[data-reason="subject:sex"]')
      .setValue('Use the report with direct clinical ascertainment.');
    await wrapper.get('[data-resolve="subject:sex"]').trigger('click');

    expect(wrapper.emitted('resolve')[0][0]).toEqual({
      conflictKey: 'subject:sex',
      candidateSetDigest: 'sha256:current',
      strategy: 'select_observations',
      selectedObservationIds: ['report-1'],
      reason: 'Use the report with direct clinical ascertainment.',
    });
  });

  it('does not carry choices into a reopened conflict with a new digest', async () => {
    const wrapper = mount(ConflictResolutionPanel, { props: { issues: [issue], observations } });
    await wrapper.get('[data-candidate="report-1"]').setValue(true);
    await wrapper.get('[data-reason="subject:sex"]').setValue('First conflict rationale.');
    await wrapper.setProps({
      issues: [{ ...issue, candidateSetDigest: 'sha256:new-candidates' }],
    });
    expect(wrapper.get('[data-candidate="report-1"]').element.checked).toBe(false);
    expect(wrapper.get('[data-reason="subject:sex"]').element.value).toBe('');
  });
});
