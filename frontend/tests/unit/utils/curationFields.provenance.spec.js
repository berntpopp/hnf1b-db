/**
 * Unit tests for the Provenance & notes section's CURATION_FIELDS entries
 * (curation console plan Task 8; design spec §3.6: ReviewBy -> curatedBy,
 * ReviewDate -> curatedAt, Comment/Problematic/DupCheck -> the three
 * free-text fields).
 *
 * `curatedBy`/`curatedAt` are auto-stamped by PhenopacketCreateEdit.vue's
 * `stampCuration()` (never a curator-facing input control -- see
 * ProvenanceSection.spec.js's "no reviewer input control" non-negotiable
 * suite for the structural proof of that). These two registry entries just
 * prove the plumbing reads the right paths; none of the five fields here has
 * a `not_reported` vocabulary concept (curatedBy/curatedAt are stamps, the
 * other three are free text), so only ordinary presence/absence is tested.
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

describe('CURATION_FIELDS — provenance section (Task 8)', () => {
  it('registers exactly the five provenance-section fields', () => {
    const provenanceFieldIds = CURATION_FIELDS.filter((f) => f.section === 'provenance').map(
      (f) => f.id
    );
    expect(provenanceFieldIds.sort()).toEqual(
      ['curatedBy', 'curatedAt', 'caseComment', 'problematic', 'duplicateCheck'].sort()
    );
  });

  describe('curatedBy', () => {
    it('reads hnf1bCuration.curatedBy', () => {
      expect(
        fieldById('curatedBy').getValue({ hnf1bCuration: { curatedBy: 'Jane Curator' } })
      ).toBe('Jane Curator');
    });

    it('is filled when set and not filled when absent', () => {
      const field = fieldById('curatedBy');
      expect(isFieldFilled(field, { hnf1bCuration: { curatedBy: 'Jane Curator' } })).toBe(true);
      expect(isFieldFilled(field, { hnf1bCuration: {} })).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });
  });

  describe('curatedAt', () => {
    it('reads hnf1bCuration.curatedAt', () => {
      expect(
        fieldById('curatedAt').getValue({
          hnf1bCuration: { curatedAt: '2026-07-31T00:00:00.000Z' },
        })
      ).toBe('2026-07-31T00:00:00.000Z');
    });

    it('is filled when set and not filled when absent', () => {
      const field = fieldById('curatedAt');
      expect(
        isFieldFilled(field, { hnf1bCuration: { curatedAt: '2026-07-31T00:00:00.000Z' } })
      ).toBe(true);
      expect(isFieldFilled(field, { hnf1bCuration: {} })).toBe(false);
    });
  });

  describe('caseComment', () => {
    it('reads hnf1bCuration.caseComment', () => {
      expect(fieldById('caseComment').getValue({ hnf1bCuration: { caseComment: 'note' } })).toBe(
        'note'
      );
    });

    it('is filled when set and not filled when absent', () => {
      const field = fieldById('caseComment');
      expect(isFieldFilled(field, { hnf1bCuration: { caseComment: 'note' } })).toBe(true);
      expect(isFieldFilled(field, { hnf1bCuration: {} })).toBe(false);
    });
  });

  describe('problematic', () => {
    it('reads hnf1bCuration.problematic', () => {
      expect(
        fieldById('problematic').getValue({ hnf1bCuration: { problematic: 'unclear zygosity' } })
      ).toBe('unclear zygosity');
    });

    it('is filled when set and not filled when absent', () => {
      const field = fieldById('problematic');
      expect(isFieldFilled(field, { hnf1bCuration: { problematic: 'x' } })).toBe(true);
      expect(isFieldFilled(field, { hnf1bCuration: {} })).toBe(false);
    });
  });

  describe('duplicateCheck', () => {
    it('reads hnf1bCuration.duplicateCheck', () => {
      expect(
        fieldById('duplicateCheck').getValue({
          hnf1bCuration: { duplicateCheck: 'checked against PMID:123' },
        })
      ).toBe('checked against PMID:123');
    });

    it('is filled when set and not filled when absent', () => {
      const field = fieldById('duplicateCheck');
      expect(isFieldFilled(field, { hnf1bCuration: { duplicateCheck: 'x' } })).toBe(true);
      expect(isFieldFilled(field, { hnf1bCuration: {} })).toBe(false);
    });
  });
});
