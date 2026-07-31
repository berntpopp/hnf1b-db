import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as vuetifyComponents from 'vuetify/components';
import * as vuetifyDirectives from 'vuetify/directives';
import { readEncounterAge } from '@/utils/age';
import SubjectCard from '@/components/phenopacket/SubjectCard.vue';

const fullVuetify = createVuetify({ components: vuetifyComponents, directives: vuetifyDirectives });

describe('readEncounterAge', () => {
  it('reads the corpus shape (flat iso8601duration)', () => {
    expect(readEncounterAge({ timeAtLastEncounter: { iso8601duration: 'P9Y4M' } })).toBe('P9Y4M');
  });

  it('reads the GA4GH-conformant shape (nested under age)', () => {
    expect(readEncounterAge({ timeAtLastEncounter: { age: { iso8601duration: 'P2Y' } } })).toBe(
      'P2Y'
    );
  });

  it('returns null when no age is present', () => {
    expect(readEncounterAge({ timeAtLastEncounter: {} })).toBeNull();
    expect(readEncounterAge({})).toBeNull();
    expect(readEncounterAge(null)).toBeNull();
  });

  it('returns null for an ontologyClass-only time element', () => {
    expect(
      readEncounterAge({
        timeAtLastEncounter: { ontologyClass: { id: 'HP:0034199', label: 'Prenatal onset' } },
      })
    ).toBeNull();
  });

  it('prefers the conformant shape when both are somehow present', () => {
    expect(
      readEncounterAge({
        timeAtLastEncounter: { iso8601duration: 'P1Y', age: { iso8601duration: 'P2Y' } },
      })
    ).toBe('P2Y');
  });
});

/**
 * Curation console Task 9 (design spec §3.5, plan Task 9): a fetus subject
 * saved via AgeSection.vue's writer -- `timeAtLastEncounter:
 * {gestationalAge: {weeks, days}}` -- must render an actual age value in
 * the mounted component, not silently fall through to "N/A" the way it did
 * before this task (readEncounterAge alone returns null for this shape by
 * design; see utils/age.js).
 */
describe('SubjectCard — gestational age (Task 9)', () => {
  function mountCard(subject) {
    return mount(SubjectCard, {
      props: { subject },
      global: { plugins: [fullVuetify] },
    });
  }

  it('renders a formatted gestational age instead of omitting the Age row', () => {
    const wrapper = mountCard({
      id: 'SUB-FETUS-1',
      sex: 'FEMALE',
      timeAtLastEncounter: { gestationalAge: { weeks: 32, days: 3 } },
    });

    expect(wrapper.text()).toContain('32 weeks 3 days');
  });

  it('omits the Age row entirely when neither a duration nor a gestational age is present', () => {
    const wrapper = mountCard({ id: 'SUB-2', sex: 'UNKNOWN_SEX' });

    expect(wrapper.text()).not.toContain('weeks');
  });
});
