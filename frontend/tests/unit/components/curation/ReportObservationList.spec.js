import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import ReportObservationList from '@/components/curation/reports/ReportObservationList.vue';

const reports = [
  {
    observationId: 'report-1',
    identifiers: { reportId: 'RPT-1' },
    publication: {
      pmid: '12345678',
      doi: '10.1000/example',
      publicationType: { raw: 'case report', sourceStatus: 'stated', value: 'case_report' },
    },
    phenotypes: [{ curationStatus: 'CURATED' }, { curationStatus: 'UNCURATED' }],
  },
];

describe('ReportObservationList', () => {
  it('shows report/publication identity, type, completeness, conflicts, and dirty state', () => {
    const wrapper = mount(ReportObservationList, {
      props: {
        observations: reports,
        selectedId: 'report-1',
        dirtyId: 'report-1',
        issues: [{ observationId: 'report-1', conflictKey: 'subject:sex' }],
      },
    });

    expect(wrapper.text()).toContain('RPT-1');
    expect(wrapper.text()).toContain('PMID:12345678');
    expect(wrapper.text()).toContain('DOI:10.1000/example');
    expect(wrapper.text()).toContain('case_report');
    expect(wrapper.text()).toContain('1/2');
    expect(wrapper.text()).toContain('1 conflict');
    expect(wrapper.text()).toContain('Unsaved');
  });

  it('emits selection by stable observation ID', async () => {
    const wrapper = mount(ReportObservationList, { props: { observations: reports } });
    await wrapper.get('button').trigger('click');
    expect(wrapper.emitted('select')).toEqual([['report-1']]);
  });
});
