import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import ReportObservationEditor from '@/components/curation/reports/ReportObservationEditor.vue';

const observed = (raw, value) => ({
  raw,
  sourceStatus: 'stated',
  value,
  correctionIds: ['correction-1'],
});

const observation = {
  observationId: 'report-1',
  origin: 'imported',
  source: {
    provider: 'google_sheets',
    datasetId: 'registry',
    sheet: 'Individuals',
    manifestSha256: 'sha256:fixture',
  },
  identifiers: {
    individualId: '317',
    sourceSubjectId: 'source-317',
    reportId: 'RPT-1',
    sex: observed('M', 'MALE'),
  },
  publication: {
    sourceKey: observed('source-key', 'source-key'),
    publicationType: observed('case report', 'case_report'),
    pmid: '123',
    doi: '10.1/a',
  },
  case: { cohort: observed('born', 'born'), familyHistory: observed('positive', 'positive') },
  ages: {
    onset: observed('28w', { kind: 'gestationalAge', iso8601Duration: 'P28W' }),
    reported: observed('12y', { kind: 'age', iso8601Duration: 'P12Y' }),
  },
  variant: {
    variantType: observed('SNV', 'SNV'),
    reported: observed('c.123A>G', 'NM_000458.4:c.123A>G'),
    sourceId: observed('variant-7', 'variant-7'),
    hg19Info: observed('chr17:36000000:A:G', 'chr17:36000000:A:G'),
    hg19: observed('17-36000000-A-G', '17-36000000-A-G'),
    hg38Info: observed('chr17:37700000:A:G', 'chr17:37700000:A:G'),
    hg38: observed('17-37700000-A-G', '17-37700000-A-G'),
    varsome: observed('https://varsome.example/source', 'https://varsome.example/source'),
    detectionMethod: observed('Sanger', 'sanger'),
    segregation: observed('de novo', 'de_novo'),
    normalized: { id: 'ga4gh:VA.test', variation: { text: { definition: 'NC_000017.11:g.1A>G' } } },
  },
  classification: { verdict: observed('Pathogenic', 'PATHOGENIC') },
  phenotypes: [],
  sourceReview: {
    reviewerId: 'reviewer-7',
    reviewerDisplayLabel: 'Reviewer Seven',
    reviewedOn: '2025-02-03',
  },
  notes: { comment: observed('source note', 'source note') },
};

describe('ReportObservationEditor', () => {
  it('shows source age, provenance, reviewer label, and every variant source field', () => {
    const wrapper = mount(ReportObservationEditor, { props: { modelValue: observation } });
    for (const text of [
      '28w',
      'P28W',
      'Reviewer Seven',
      'google_sheets',
      'c.123A>G',
      'chr17:36000000:A:G',
      '17-36000000-A-G',
      'chr17:37700000:A:G',
      '17-37700000-A-G',
      'https://varsome.example/source',
      'Sanger',
      'de novo',
      'ga4gh:VA.test',
      'source note',
    ]) {
      expect(wrapper.text()).toContain(text);
    }
    expect(wrapper.text()).not.toContain('@');
  });

  it('updates publication identity without dropping age, variant, review, or notes metadata', async () => {
    const wrapper = mount(ReportObservationEditor, { props: { modelValue: observation } });
    await wrapper.get('[name="doi"]').setValue('10.2/revised');
    const emitted = wrapper.emitted('update:modelValue').at(-1)[0];
    expect(emitted.publication.doi).toBe('10.2/revised');
    expect(emitted.ages).toEqual(observation.ages);
    expect(emitted.variant).toEqual(observation.variant);
    expect(emitted.sourceReview).toEqual(observation.sourceReview);
    expect(emitted.notes).toEqual(observation.notes);
  });
});
