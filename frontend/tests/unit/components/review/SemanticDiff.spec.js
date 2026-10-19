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

  it('renders clinical change summary cards resolving human-friendly terms and deltas', () => {
    const richChanges = [
      {
        section: 'Phenotypes',
        operation: 'changed',
        path: '/phenotypicFeatures/0/excluded',
        before: false,
        after: true,
      },
      {
        section: 'Variants/Interpretations',
        operation: 'changed',
        path: '/interpretations/0/diagnosis/genomicInterpretations/0/variantInterpretation/acmgPathogenicityClassification',
        before: 'VUS',
        after: 'PATHOGENIC',
      },
      {
        section: 'Subject',
        operation: 'changed',
        path: '/subject/sex',
        before: 'MALE',
        after: 'FEMALE',
      },
    ];

    const candidate = {
      content: {
        phenotypicFeatures: [{ type: { id: 'HP:0000107', label: 'Renal cyst' } }],
        interpretations: [
          {
            diagnosis: {
              genomicInterpretations: [
                {
                  variantInterpretation: {
                    variationDescriptor: {
                      id: 'var-1',
                      label: 'c.827G>A',
                      geneContext: { value: 'HNF1B' },
                    },
                  },
                },
              ],
            },
          },
        ],
      },
    };

    const wrapper = mount(SemanticDiff, {
      props: { changes: richChanges, baseline: { id: 8 }, candidate },
    });

    const summary = wrapper.find('[data-testid="clinical-summary"]');
    expect(summary.exists()).toBe(true);
    expect(summary.text()).toContain('Phenotypes Added / Removed / Excluded');
    expect(summary.text()).toContain('HP:0000107 — Renal cyst (Present -> Excluded)');
    expect(summary.text()).toContain('Variant / ACMG Classification Changes');
    expect(summary.text()).toContain('HNF1B c.827G>A — ACMG classification: VUS -> PATHOGENIC');
    expect(summary.text()).toContain('Subject / Onset Deltas');
    expect(summary.text()).toContain('Subject sex: MALE -> FEMALE');
  });

  it('toggles raw RFC-6902 path visibility with data-testid="toggle-raw-diff" while keeping elements accessible in DOM', async () => {
    const wrapper = mount(SemanticDiff, { props: { changes, baseline: { id: 8 } } });

    const toggleBtn = wrapper.find('[data-testid="toggle-raw-diff"]');
    expect(toggleBtn.exists()).toBe(true);
    expect(toggleBtn.text()).toContain('Hide RFC-6902 paths');

    const sectionsEl = wrapper.find('.semantic-diff__sections');
    expect(sectionsEl.isVisible()).toBe(true);
    expect(wrapper.findAll('.semantic-change').length).toBe(3);

    await toggleBtn.trigger('click');
    expect(toggleBtn.text()).toContain('Show RFC-6902 paths');
    expect(wrapper.find('.semantic-diff__sections').attributes('style')).toContain('display: none');
    // Elements remain in DOM for accessibility and tests
    expect(wrapper.findAll('.semantic-change').length).toBe(3);

    await toggleBtn.trigger('click');
    expect(toggleBtn.text()).toContain('Hide RFC-6902 paths');
    expect(wrapper.find('.semantic-diff__sections').attributes('style') || '').not.toContain(
      'display: none'
    );
  });
});
