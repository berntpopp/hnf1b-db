/**
 * Unit tests for the Age & onset section's CURATION_FIELDS entries (curation
 * console plan Task 8; design spec §3.5: AgeOnset -> diseases[0].onset,
 * AgeReported -> subject.timeAtLastEncounter).
 *
 * Both fields are GA4GH TimeElement objects. Unlike the vocabulary-backed
 * fields Tasks 4/5/6 registered, a TimeElement has no `not_reported` concept
 * -- GA4GH doesn't model "the source is silent about onset" as a selectable
 * value the way `familyHistory`/`detectionMethod` do. These tests therefore
 * only prove ordinary presence/absence, not the not_reported-vs-absent
 * distinction (see the plan's Task 8 TDD note).
 */
import { describe, it, expect } from 'vitest';
import { CURATION_FIELDS, isFieldFilled } from '@/utils/curationFields';

function fieldById(id) {
  const field = CURATION_FIELDS.find((f) => f.id === id);
  if (!field) {
    throw new Error(`No CURATION_FIELDS entry registered with id "${id}"`);
  }
  return field;
}

describe('CURATION_FIELDS — age section (Task 8)', () => {
  it('registers exactly the two age-section fields', () => {
    const ageFieldIds = CURATION_FIELDS.filter((f) => f.section === 'age').map((f) => f.id);
    expect(ageFieldIds.sort()).toEqual(['ageOnset', 'ageReported'].sort());
  });

  describe('ageOnset', () => {
    it('reads diseases[0].onset', () => {
      const onset = { ontologyClass: { id: 'HP:0003577', label: 'Congenital onset' } };
      expect(fieldById('ageOnset').getValue({ diseases: [{ onset }] })).toBe(onset);
    });

    it('is filled when set (congenital shape)', () => {
      const field = fieldById('ageOnset');
      expect(
        isFieldFilled(field, {
          diseases: [{ onset: { ontologyClass: { id: 'HP:0003577' } } }],
        })
      ).toBe(true);
    });

    it('is filled when set (nested age shape -- the corpus convention for onset)', () => {
      const field = fieldById('ageOnset');
      expect(
        isFieldFilled(field, { diseases: [{ onset: { age: { iso8601duration: 'P5Y' } } }] })
      ).toBe(true);
    });

    it('is filled when set (gestational shape)', () => {
      const field = fieldById('ageOnset');
      expect(
        isFieldFilled(field, {
          diseases: [{ onset: { gestationalAge: { weeks: 32, days: 3 } } }],
        })
      ).toBe(true);
    });

    it('is not filled when absent', () => {
      const field = fieldById('ageOnset');
      expect(isFieldFilled(field, { diseases: [{}] })).toBe(false);
      expect(isFieldFilled(field, { diseases: [] })).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });
  });

  describe('ageReported', () => {
    it('reads subject.timeAtLastEncounter', () => {
      const t = { iso8601duration: 'P41Y' };
      expect(fieldById('ageReported').getValue({ subject: { timeAtLastEncounter: t } })).toBe(t);
    });

    it('is filled when set (flat shape -- the corpus convention, ADR 0003 D4)', () => {
      const field = fieldById('ageReported');
      expect(
        isFieldFilled(field, { subject: { timeAtLastEncounter: { iso8601duration: 'P41Y' } } })
      ).toBe(true);
    });

    it('is not filled when absent', () => {
      const field = fieldById('ageReported');
      expect(isFieldFilled(field, { subject: {} })).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });
  });
});
