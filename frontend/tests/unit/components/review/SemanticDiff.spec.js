import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';

import SemanticDiff from '@/components/review/SemanticDiff.vue';

const changes = [
  { section: 'Subject', operation: 'added', path: '/subject/sex', before: null, after: 'FEMALE' },
  {
    section: 'Phenotypes',
    operation: 'removed',
    path: '/phenotypicFeatures/1',
    before: { type: { id: 'HP:2' } },
    after: null,
  },
  {
    section: 'Measurements',
    operation: 'changed',
    path: '/measurements/0/value',
    before: '<img src=x onerror=alert(1)>',
    after: 2,
  },
];

describe('SemanticDiff', () => {
  it('renders backend operations with text, icons, and accessible paths', () => {
    const wrapper = mount(SemanticDiff, { props: { changes, baseline: { id: 8 } } });

    expect(wrapper.text()).toContain('Added');
    expect(wrapper.text()).toContain('Removed');
    expect(wrapper.text()).toContain('Changed');
    expect(wrapper.find('[data-operation="added"] .operation-icon').text()).toContain('mdi-plus');
    expect(wrapper.find('[data-operation="removed"] .operation-icon').text()).toContain(
      'mdi-minus'
    );
    expect(wrapper.find('[data-operation="changed"] .operation-icon').text()).toContain('mdi-swap');
    expect(wrapper.get('[data-operation="changed"]').attributes('aria-label')).toContain(
      'Changed at JSON pointer /measurements/0/value'
    );
  });

  it('shows before and after labels so meaning never depends on color', () => {
    const wrapper = mount(SemanticDiff, { props: { changes, baseline: { id: 8 } } });

    expect(wrapper.text()).toContain('Before');
    expect(wrapper.text()).toContain('After');
    expect(wrapper.find('img').exists()).toBe(false);
    expect(wrapper.html()).not.toContain('onerror');
  });

  it('labels a null baseline as a new phenopacket', () => {
    const wrapper = mount(SemanticDiff, { props: { changes: [], baseline: null } });

    expect(wrapper.text()).toContain('New phenopacket');
  });

  it('groups changes by clinical section and provides section headers', () => {
    const wrapper = mount(SemanticDiff, { props: { changes, baseline: { id: 8 } } });

    expect(wrapper.text()).toContain('Subject');
    expect(wrapper.text()).toContain('Phenotypes');
    expect(wrapper.text()).toContain('Measurements');
    expect(wrapper.findAll('.section-group').length).toBe(3);
  });
});
