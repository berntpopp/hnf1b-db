/**
 * Unit tests for PhenotypicFeaturesCard.vue (curation console plan Task 9).
 *
 * Logged during Phase 2 monkey testing: a record with 5 stored features (2
 * `excluded: true`) rendered "Phenotypic Features (3)" with the word
 * "excluded" appearing nowhere in the DOM -- `presentFeatures` silently
 * dropped excluded features from both the chip list AND the header count.
 * At corpus scale this is not a rare edge case (HP:0100611 has 68 excluded
 * vs 35 present; ORPHA:2260 has 68 vs 7). `excluded: true` is a stronger
 * clinical claim than silence and must be visible and counted.
 */
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as vuetifyComponents from 'vuetify/components';
import * as vuetifyDirectives from 'vuetify/directives';
import PhenotypicFeaturesCard from '@/components/phenopacket/PhenotypicFeaturesCard.vue';

const fullVuetify = createVuetify({ components: vuetifyComponents, directives: vuetifyDirectives });

function mountCard(features) {
  return mount(PhenotypicFeaturesCard, {
    props: { features },
    global: { plugins: [fullVuetify] },
  });
}

const FIVE_FEATURES_TWO_EXCLUDED = [
  { type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: false },
  { type: { id: 'HP:0000108', label: 'Renal corticomedullary cysts' }, excluded: false },
  { type: { id: 'HP:0000122', label: 'Unilateral renal agenesis' }, excluded: false },
  { type: { id: 'HP:0100611', label: 'Multiple glomerular cysts' }, excluded: true },
  { type: { id: 'HP:0000079', label: 'Abnormality of the urinary system' }, excluded: true },
];

describe('PhenotypicFeaturesCard — excluded features (Task 9)', () => {
  it('renders all 5 features (not just the 3 present ones)', () => {
    const wrapper = mountCard(FIVE_FEATURES_TWO_EXCLUDED);

    const chips = wrapper.findAll('.feature-chip');
    expect(chips).toHaveLength(5);
  });

  it('labels exactly the excluded features as excluded, and no others', () => {
    const wrapper = mountCard(FIVE_FEATURES_TWO_EXCLUDED);

    const excludedLabels = wrapper.findAll('.feature-excluded-label');
    expect(excludedLabels).toHaveLength(2);

    const chips = wrapper.findAll('.feature-chip');
    const excludedChipText = chips
      .filter((chip) => chip.find('.feature-excluded-label').exists())
      .map((chip) => chip.text());
    expect(excludedChipText).toEqual([
      expect.stringContaining('Multiple glomerular cysts'),
      expect.stringContaining('Abnormality of the urinary system'),
    ]);
  });

  it('header count reflects everything rendered (3 present, 2 excluded), not a silently dropped 3', () => {
    const wrapper = mountCard(FIVE_FEATURES_TWO_EXCLUDED);

    expect(wrapper.text()).toContain('Phenotypic Features (3 present, 2 excluded)');
    // The old, buggy header this replaces -- pin that it never regresses.
    expect(wrapper.text()).not.toContain('Phenotypic Features (3)');
  });

  it('omits the present/excluded breakdown when nothing is excluded', () => {
    const wrapper = mountCard([
      { type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: false },
      { type: { id: 'HP:0000108', label: 'Renal corticomedullary cysts' }, excluded: false },
    ]);

    expect(wrapper.text()).toContain('Phenotypic Features (2)');
    expect(wrapper.text()).not.toContain('excluded');
  });

  it('shows the empty state only when there are truly zero features (present or excluded)', () => {
    const wrapper = mountCard([]);

    expect(wrapper.text()).toContain('No phenotypic features recorded');
    expect(wrapper.findAll('.feature-chip')).toHaveLength(0);
  });

  it('does not show the empty state when every feature is excluded', () => {
    const wrapper = mountCard([
      { type: { id: 'HP:0100611', label: 'Multiple glomerular cysts' }, excluded: true },
    ]);

    expect(wrapper.text()).not.toContain('No phenotypic features recorded');
    expect(wrapper.text()).toContain('Phenotypic Features (0 present, 1 excluded)');
  });

  it('applies strikethrough styling to excluded feature names, not present ones', () => {
    const wrapper = mountCard(FIVE_FEATURES_TWO_EXCLUDED);

    const names = wrapper.findAll('.feature-name');
    const struckThrough = names.filter((n) => n.classes().includes('text-decoration-line-through'));
    expect(struckThrough).toHaveLength(2);
  });

  it('uses the error semantic color (not a hardcoded hex/lighten class) for excluded chips', () => {
    const wrapper = mountCard(FIVE_FEATURES_TWO_EXCLUDED);

    const excludedChip = wrapper
      .findAllComponents({ name: 'VChip' })
      .find((c) => c.props('color') === 'error');
    expect(excludedChip).toBeTruthy();
  });
});
