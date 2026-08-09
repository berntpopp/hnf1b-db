import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import CanonicalProjectionPreview from '@/components/curation/reports/CanonicalProjectionPreview.vue';

describe('CanonicalProjectionPreview', () => {
  it('renders the deterministic server projection summary and digest', () => {
    const wrapper = mount(CanonicalProjectionPreview, {
      props: {
        projection: {
          phenopacket: {
            subject: { id: '317', sex: 'FEMALE' },
            phenotypicFeatures: [{ type: { id: 'HP:0000107' } }],
            interpretations: [{ id: 'variant-1' }],
            metaData: { externalReferences: [{ id: 'PMID:123' }, { id: 'DOI:10.1/a' }] },
          },
          outputDigest: 'sha256:output',
          issues: [{ conflictKey: 'subject:sex' }],
        },
      },
    });

    for (const text of [
      '317',
      'FEMALE',
      '1 phenotype',
      '1 variant',
      'PMID:123',
      'DOI:10.1/a',
      '1 conflict',
      'sha256:output',
    ]) {
      expect(wrapper.text()).toContain(text);
    }
  });
});
