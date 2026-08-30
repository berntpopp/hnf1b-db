import { describe, expect, it } from 'vitest';
import { shallowMount } from '@vue/test-utils';

import CandidateSnapshot from '@/components/review/CandidateSnapshot.vue';

const content = {
  id: 'PP-1',
  subject: { id: 'S-1', sex: 'FEMALE' },
  phenotypicFeatures: [{ type: { id: 'HP:0001250', label: 'Seizure' } }],
  diseases: [{ term: { id: 'MONDO:0015967', label: 'RCAD' } }],
  interpretations: [{ id: 'I-1', progressStatus: 'SOLVED' }],
  measurements: [{ id: 'M-1', value: { quantity: { value: 1 } } }],
  metaData: { created: '2026-08-14T00:00:00Z' },
  customExtension: { raw: '<script>alert(1)</script>', preserved: true },
};

describe('CandidateSnapshot', () => {
  it('renders the candidate Phenopacket identifier as first-class content', () => {
    const wrapper = shallowMount(CandidateSnapshot, { props: { candidate: { id: 42, content } } });

    expect(wrapper.get('[data-testid="candidate-phenopacket-id"]').text()).toBe('PP-1');
  });

  it('passes the complete candidate to every established display card', () => {
    const wrapper = shallowMount(CandidateSnapshot, { props: { candidate: { id: 42, content } } });

    expect(wrapper.getComponent({ name: 'SubjectCard' }).props('subject')).toEqual(content.subject);
    expect(wrapper.getComponent({ name: 'PhenotypicFeaturesCard' }).props('features')).toEqual(
      content.phenotypicFeatures
    );
    expect(wrapper.getComponent({ name: 'DiseasesCard' }).props('diseases')).toEqual(
      content.diseases
    );
    expect(wrapper.getComponent({ name: 'InterpretationsCard' }).props('interpretations')).toEqual(
      content.interpretations
    );
    expect(wrapper.getComponent({ name: 'MeasurementsCard' }).props('measurements')).toEqual(
      content.measurements
    );
    expect(wrapper.getComponent({ name: 'MetadataCard' }).props('metaData')).toEqual(
      content.metaData
    );
  });

  it('shows sanitized raw extension content without dropping its data', () => {
    const wrapper = shallowMount(CandidateSnapshot, { props: { candidate: { id: 42, content } } });

    expect(wrapper.text()).toContain('Raw extension content');
    expect(wrapper.text()).toContain('customExtension');
    expect(wrapper.text()).toContain('preserved');
    expect(wrapper.html()).not.toContain('<script>');
  });
});
