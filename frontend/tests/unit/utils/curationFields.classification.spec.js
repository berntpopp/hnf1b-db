/**
 * Unit tests for the Classification section's CURATION_FIELDS entries
 * (curation console plan Task 6; design spec §3.3: verdict_classification,
 * criteria_classification, system_classification, date_classification,
 * comment_classification).
 *
 * Vocabulary check (per the Task 6 briefing -- confirm before writing a
 * not_reported-vs-absent assertion): neither `interpretation-status`
 * (backend/alembic/versions/88b3a0c19a89_add_phenopacket_controlled_vocabularies.py)
 * nor `classification-system`
 * (backend/alembic/versions/e7f710e344d2_add_curation_console_vocabularies.py)
 * has a `not_reported` member. `verdict` and `classificationSystem` are
 * therefore tested for ordinary presence/absence only, like
 * `classificationDate`/`classificationComment`/`criteria` (all free text with
 * no vocabulary concept at all).
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

/** Build a phenopacket carrying a single interpretation with the given genomicInterpretation. */
function withGenomicInterpretation(genomicInterpretation) {
  return {
    interpretations: [
      {
        diagnosis: {
          genomicInterpretations: [genomicInterpretation],
        },
      },
    ],
  };
}

describe('CURATION_FIELDS — classification section (Task 6)', () => {
  it('registers exactly the five classification-section fields', () => {
    const classificationFieldIds = CURATION_FIELDS.filter(
      (f) => f.section === 'classification'
    ).map((f) => f.id);
    expect(classificationFieldIds.sort()).toEqual(
      [
        'verdict',
        'criteria',
        'classificationSystem',
        'classificationDate',
        'classificationComment',
      ].sort()
    );
  });

  describe('verdict', () => {
    it('reads interpretationStatus off the first genomicInterpretation -- a SIBLING of variantInterpretation, not under variationDescriptor', () => {
      const field = fieldById('verdict');
      const phenopacket = withGenomicInterpretation({
        interpretationStatus: 'PATHOGENIC',
        variantInterpretation: { variationDescriptor: { id: 'var:1' } },
      });
      expect(field.getValue(phenopacket)).toBe('PATHOGENIC');
    });

    it('is filled for a real vocabulary value and not filled when absent', () => {
      const field = fieldById('verdict');
      expect(
        isFieldFilled(field, withGenomicInterpretation({ interpretationStatus: 'LIKELY_BENIGN' }))
      ).toBe(true);
      expect(isFieldFilled(field, withGenomicInterpretation({}))).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });

    it('treats the "UNKNOWN" seed value (Task 5\'s default for every new variant) as NOT filled -- unlike sex\'s UNKNOWN_SEX, "UNKNOWN" is not a member of the interpretation-status vocabulary at all, just an uninitialized placeholder', () => {
      const field = fieldById('verdict');
      expect(
        isFieldFilled(field, withGenomicInterpretation({ interpretationStatus: 'UNKNOWN' }))
      ).toBe(false);
    });
  });

  describe('criteria', () => {
    it('reads variantInterpretation.extensions[classification_criteria].value.criteria -- NOT variationDescriptor.extensions, where segregation/coordinates live', () => {
      const field = fieldById('criteria');
      const phenopacket = withGenomicInterpretation({
        variantInterpretation: {
          extensions: [
            {
              name: 'classification_criteria',
              value: { criteria: 'PM1_Moderate, PM2_Supporting', guidelines: 'ACMG' },
            },
          ],
        },
      });
      expect(field.getValue(phenopacket)).toBe('PM1_Moderate, PM2_Supporting');
    });

    it('is filled when set and not filled when absent', () => {
      const field = fieldById('criteria');
      expect(
        isFieldFilled(
          field,
          withGenomicInterpretation({
            variantInterpretation: {
              extensions: [
                { name: 'classification_criteria', value: { criteria: 'BP4_Supporting' } },
              ],
            },
          })
        )
      ).toBe(true);
      expect(
        isFieldFilled(
          field,
          withGenomicInterpretation({ variantInterpretation: { extensions: [] } })
        )
      ).toBe(false);
      expect(isFieldFilled(field, withGenomicInterpretation({ variantInterpretation: {} }))).toBe(
        false
      );
      expect(isFieldFilled(field, withGenomicInterpretation({}))).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });

    it('is not fooled by a same-named extension living on variationDescriptor instead', () => {
      const field = fieldById('criteria');
      const phenopacket = withGenomicInterpretation({
        variantInterpretation: {
          variationDescriptor: {
            extensions: [
              { name: 'classification_criteria', value: { criteria: 'wrong location' } },
            ],
          },
        },
      });
      expect(field.getValue(phenopacket)).toBeUndefined();
    });
  });

  describe('classificationSystem', () => {
    it('reads hnf1bCuration.classificationSystem', () => {
      expect(
        fieldById('classificationSystem').getValue({
          hnf1bCuration: { classificationSystem: 'acmg' },
        })
      ).toBe('acmg');
    });

    it('is filled when set and not filled when absent', () => {
      const field = fieldById('classificationSystem');
      expect(isFieldFilled(field, { hnf1bCuration: { classificationSystem: 'clingen_cnv' } })).toBe(
        true
      );
      expect(isFieldFilled(field, { hnf1bCuration: {} })).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });
  });

  describe('classificationDate', () => {
    it('reads hnf1bCuration.classificationDate', () => {
      expect(
        fieldById('classificationDate').getValue({
          hnf1bCuration: { classificationDate: '2024-03-01' },
        })
      ).toBe('2024-03-01');
    });

    it('is filled when set and not filled when absent -- free text/date, no vocabulary concept of not_reported', () => {
      const field = fieldById('classificationDate');
      expect(isFieldFilled(field, { hnf1bCuration: { classificationDate: '2024-03-01' } })).toBe(
        true
      );
      expect(isFieldFilled(field, { hnf1bCuration: {} })).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });
  });

  describe('classificationComment', () => {
    it('reads hnf1bCuration.classificationComment', () => {
      expect(
        fieldById('classificationComment').getValue({
          hnf1bCuration: { classificationComment: 'Reclassified after functional study.' },
        })
      ).toBe('Reclassified after functional study.');
    });

    it('is filled when set and not filled when absent -- free text, no vocabulary concept of not_reported', () => {
      const field = fieldById('classificationComment');
      expect(isFieldFilled(field, { hnf1bCuration: { classificationComment: 'note' } })).toBe(true);
      expect(isFieldFilled(field, { hnf1bCuration: {} })).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });
  });

  it('only ever tracks the primary/first variant, ignoring a second interpretation entirely', () => {
    const field = fieldById('verdict');
    const phenopacket = {
      interpretations: [
        {
          diagnosis: {
            genomicInterpretations: [{ interpretationStatus: 'PATHOGENIC' }],
          },
        },
        {
          diagnosis: {
            genomicInterpretations: [{ interpretationStatus: 'BENIGN' }],
          },
        },
      ],
    };
    expect(field.getValue(phenopacket)).toBe('PATHOGENIC');
  });
});
