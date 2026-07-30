/**
 * Unit tests for the Case section's CURATION_FIELDS entries (curation
 * console plan Task 4; design spec §3.1: Cohort, Sex, IndividualIdentifier,
 * Publication, PublicationType, FamilyHistory).
 *
 * These exercise the actual registered entries (not synthetic fixtures like
 * CompletenessRail.spec.js's Task-3 suite) to reinforce the programme's
 * central semantic for this section's own fields: **absence != `not_reported`**.
 * Absent means "not yet curated"; `not_reported` is an ordinary selected
 * value and must count as filled, exactly like any other value.
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

describe('CURATION_FIELDS — case section (Task 4)', () => {
  it('registers exactly the six case-section fields', () => {
    const caseFieldIds = CURATION_FIELDS.filter((f) => f.section === 'case').map((f) => f.id);
    expect(caseFieldIds.sort()).toEqual(
      [
        'cohort',
        'sex',
        'individualIdentifiers',
        'publication',
        'publicationType',
        'familyHistory',
      ].sort()
    );
  });

  describe('cohort', () => {
    it('reads hnf1bCuration.cohort', () => {
      expect(fieldById('cohort').getValue({ hnf1bCuration: { cohort: 'born' } })).toBe('born');
    });

    it('is filled when set and not filled when absent', () => {
      const field = fieldById('cohort');
      expect(isFieldFilled(field, { hnf1bCuration: { cohort: 'born' } })).toBe(true);
      expect(isFieldFilled(field, { hnf1bCuration: {} })).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });
  });

  describe('sex', () => {
    it('reads subject.sex', () => {
      expect(fieldById('sex').getValue({ subject: { sex: 'FEMALE' } })).toBe('FEMALE');
    });

    it('treats the default literal UNKNOWN_SEX as filled — it is a legitimate GA4GH enum value', () => {
      const field = fieldById('sex');
      expect(isFieldFilled(field, { subject: { sex: 'UNKNOWN_SEX' } })).toBe(true);
    });

    it('is not filled when subject/sex is absent', () => {
      const field = fieldById('sex');
      expect(isFieldFilled(field, { subject: {} })).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });
  });

  describe('individualIdentifiers', () => {
    it('reads subject.alternateIds', () => {
      expect(
        fieldById('individualIdentifiers').getValue({ subject: { alternateIds: ['Proband1'] } })
      ).toEqual(['Proband1']);
    });

    it('is filled iff the array is non-empty (default array rule)', () => {
      const field = fieldById('individualIdentifiers');
      expect(isFieldFilled(field, { subject: { alternateIds: ['Proband1'] } })).toBe(true);
      expect(isFieldFilled(field, { subject: { alternateIds: [] } })).toBe(false);
      expect(isFieldFilled(field, { subject: {} })).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });
  });

  describe('publication', () => {
    it('reads metaData.externalReferences', () => {
      const refs = [{ id: 'PMID:123' }];
      expect(fieldById('publication').getValue({ metaData: { externalReferences: refs } })).toBe(
        refs
      );
    });

    it('is filled when at least one real PMID reference is present', () => {
      const field = fieldById('publication');
      expect(isFieldFilled(field, { metaData: { externalReferences: [{ id: 'PMID:123' }] } })).toBe(
        true
      );
    });

    it('is NOT filled by a non-PMID external reference alone', () => {
      const field = fieldById('publication');
      expect(
        isFieldFilled(field, {
          metaData: { externalReferences: [{ id: 'DOI:10.1000/example' }] },
        })
      ).toBe(false);
    });

    it('guards against an empty-PMID entry ("PMID:") counting as filled', () => {
      const field = fieldById('publication');
      expect(isFieldFilled(field, { metaData: { externalReferences: [{ id: 'PMID:' }] } })).toBe(
        false
      );
    });

    it('is not filled when externalReferences is absent or empty', () => {
      const field = fieldById('publication');
      expect(isFieldFilled(field, {})).toBe(false);
      expect(isFieldFilled(field, { metaData: { externalReferences: [] } })).toBe(false);
    });
  });

  describe('publicationType', () => {
    it('reads hnf1bCuration.publicationType', () => {
      expect(
        fieldById('publicationType').getValue({ hnf1bCuration: { publicationType: 'case_report' } })
      ).toBe('case_report');
    });

    it('counts the literal string "not_reported" as filled, and absence as not filled', () => {
      const field = fieldById('publicationType');
      expect(isFieldFilled(field, { hnf1bCuration: { publicationType: 'not_reported' } })).toBe(
        true
      );
      expect(isFieldFilled(field, { hnf1bCuration: {} })).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });
  });

  describe('familyHistory — central semantic: absence != not_reported', () => {
    it('reads hnf1bCuration.familyHistory', () => {
      expect(
        fieldById('familyHistory').getValue({ hnf1bCuration: { familyHistory: 'positive' } })
      ).toBe('positive');
    });

    it('counts the literal string "not_reported" as FILLED', () => {
      const field = fieldById('familyHistory');
      expect(isFieldFilled(field, { hnf1bCuration: { familyHistory: 'not_reported' } })).toBe(true);
    });

    it('counts an absent familyHistory as NOT filled', () => {
      const field = fieldById('familyHistory');
      expect(isFieldFilled(field, { hnf1bCuration: {} })).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });

    it('never conflates an explicit not_reported value with an absent field', () => {
      const field = fieldById('familyHistory');
      const filled = isFieldFilled(field, { hnf1bCuration: { familyHistory: 'not_reported' } });
      const absent = isFieldFilled(field, {});
      expect(filled).not.toBe(absent);
    });
  });
});
