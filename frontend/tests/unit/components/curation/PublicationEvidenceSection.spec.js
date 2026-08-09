import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import PublicationEvidenceSection from '@/components/curation/reports/PublicationEvidenceSection.vue';

const publication = {
  sourceKey: {
    raw: 'internal-reference-7',
    sourceStatus: 'stated',
    value: 'internal-reference-7',
    correctionIds: ['correction-source'],
  },
  publicationType: {
    raw: 'Case report and review',
    sourceStatus: 'stated',
    value: 'case_report',
    correctionIds: ['correction-type'],
  },
  pmid: '12345678',
  doi: '10.1000/example',
};

describe('PublicationEvidenceSection', () => {
  it('renders immutable raw source values and complete PMID/DOI identity', () => {
    const wrapper = mount(PublicationEvidenceSection, { props: { modelValue: publication } });
    expect(wrapper.text()).toContain('internal-reference-7');
    expect(wrapper.text()).toContain('Case report and review');
    expect(wrapper.find('[name="pmid"]').element.value).toBe('12345678');
    expect(wrapper.find('[name="doi"]').element.value).toBe('10.1000/example');
  });

  it('edits DOI without deleting PMID, type, raw values, or correction IDs', async () => {
    const wrapper = mount(PublicationEvidenceSection, { props: { modelValue: publication } });
    await wrapper.find('[name="doi"]').setValue('10.2000/revised');
    const emitted = wrapper.emitted('update:modelValue').at(-1)[0];
    expect(emitted).toEqual({ ...publication, doi: '10.2000/revised' });
  });
});
