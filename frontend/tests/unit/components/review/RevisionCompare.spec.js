import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';

import RevisionCompare from '@/components/review/RevisionCompare.vue';

const CandidateSnapshotStub = {
  props: ['candidate'],
  template: '<div data-testid="candidate-snapshot-stub">{{ candidate?.id || "snapshot" }}</div>',
};

const stubs = {
  CandidateSnapshot: CandidateSnapshotStub,
  'v-chip': { template: '<span><slot /></span>' },
  'v-icon': { template: '<i />' },
  'v-btn-toggle': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<div><slot /></div>',
  },
  'v-btn': {
    props: ['value'],
    emits: ['click'],
    template: '<button @click="$parent.$emit(`update:modelValue`, value)"><slot /></button>',
  },
};

describe('RevisionCompare', () => {
  const baseline = {
    id: 10,
    content: {
      id: 'PP-001',
      subject: { id: 'old-subject', sex: 'MALE' },
    },
  };

  const candidate = {
    id: 12,
    revision_number: 2,
    content: {
      id: 'PP-001',
      subject: { id: 'new-subject', sex: 'FEMALE' },
      hnf1bCuration: { status: 'curated' },
    },
  };

  const changes = [
    {
      section: 'Subject',
      operation: 'changed',
      path: '/subject/id',
      before: 'old-subject',
      after: 'new-subject',
    },
    {
      section: 'Subject',
      operation: 'changed',
      path: '/subject/sex',
      before: 'MALE',
      after: 'FEMALE',
    },
  ];

  it('renders side-by-side snapshot comparison for baseline and candidate', () => {
    const wrapper = mount(RevisionCompare, {
      props: { baseline, candidate, changes },
      global: { stubs },
    });

    expect(wrapper.text()).toContain('Side-by-Side Revision Compare');
    expect(wrapper.find('[data-testid="clinical-snapshot-compare"]').exists()).toBe(true);

    const snapshots = wrapper.findAll('[data-testid="candidate-snapshot-stub"]');
    expect(snapshots.length).toBe(2);
    expect(snapshots[0].text()).toBe('10');
    expect(snapshots[1].text()).toBe('12');
  });

  it('highlights changed JSON lines in baseline and candidate JSON', () => {
    const wrapper = mount(RevisionCompare, {
      props: { baseline, candidate, changes },
      global: { stubs },
    });

    const baselineJson = wrapper.get('[data-testid="baseline-json-lines"]');
    const candidateJson = wrapper.get('[data-testid="candidate-json-lines"]');

    expect(baselineJson.text()).toContain('old-subject');
    expect(candidateJson.text()).toContain('new-subject');

    const highlightedBaseline = baselineJson.findAll('.json-line--highlighted');
    expect(highlightedBaseline.length).toBeGreaterThan(0);

    const highlightedCandidate = candidateJson.findAll('.json-line--highlighted');
    expect(highlightedCandidate.length).toBeGreaterThan(0);
  });

  it('displays empty baseline message when baseline is null (new phenopacket)', () => {
    const wrapper = mount(RevisionCompare, {
      props: { baseline: null, candidate, changes: [] },
      global: { stubs },
    });

    expect(wrapper.find('[data-testid="no-baseline-snapshot"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="no-baseline-json"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('No published baseline');
  });

  it('allows toggling between Both, Clinical Snapshot, and JSON Lines view modes', async () => {
    const wrapper = mount(RevisionCompare, {
      props: { baseline, candidate, changes },
      global: { stubs },
    });

    expect(wrapper.find('[data-testid="clinical-snapshot-compare"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="json-lines-compare"]').exists()).toBe(true);

    // Switch to snapshot only
    const buttons = wrapper.findAll('button');
    const snapshotBtn = buttons.find((b) => b.text() === 'Clinical Snapshot');
    await snapshotBtn.trigger('click');

    expect(wrapper.find('[data-testid="clinical-snapshot-compare"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="json-lines-compare"]').exists()).toBe(false);

    // Switch to json only
    const jsonBtn = buttons.find((b) => b.text() === 'JSON Lines');
    await jsonBtn.trigger('click');

    expect(wrapper.find('[data-testid="clinical-snapshot-compare"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="json-lines-compare"]').exists()).toBe(true);
  });
});
