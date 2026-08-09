import { describe, expect, it } from 'vitest';

import {
  assessmentCompleteness,
  cloneObservation,
  correctionTargets,
  getLaterality,
  setAssessmentStatus,
  setLaterality,
  updateObservedValue,
} from '@/utils/curationAdapters';

const unilateralLeft = [
  { id: 'HP:0012833', label: 'Unilateral' },
  { id: 'HP:0012835', label: 'Left' },
];

function assessment(overrides = {}) {
  return {
    assessmentId: 'assessment-1',
    column: 'RenalCysts',
    rawValue: 'unilateral left',
    sourceStatus: 'stated',
    curationStatus: 'CURATED',
    assessmentStatus: 'PRESENT',
    findings: [
      {
        definitionId: 'renal-cyst',
        term: { id: 'HP:0000107', label: 'Renal cyst' },
        sourceTerm: { id: 'LOCAL:renal-cyst', label: 'Renal cyst source label' },
        modifiers: unilateralLeft,
      },
    ],
    evidence: [
      {
        reference: 'DOI:10.1000/example',
        evidenceCode: { id: 'ECO:0006013', label: 'traceable author statement' },
      },
    ],
    correctionIds: ['correction-1'],
    ...overrides,
  };
}

describe('lossless curation DTO adapters', () => {
  it('deep-clones a report so local edits cannot mutate the loaded ledger', () => {
    const source = {
      observationId: 'report-1',
      publication: {
        sourceKey: { raw: 'internal-7', sourceStatus: 'stated', value: 'internal-7' },
        publicationType: { raw: 'case report', sourceStatus: 'stated', value: 'case_report' },
        pmid: '12345678',
        doi: '10.1000/example',
      },
      phenotypes: [assessment()],
    };

    const draft = cloneObservation(source);
    draft.publication.pmid = '87654321';
    draft.phenotypes[0].evidence[0].reference = 'PMID:87654321';

    expect(source.publication.pmid).toBe('12345678');
    expect(source.phenotypes[0].evidence[0].reference).toBe('DOI:10.1000/example');
    expect(draft.publication).toMatchObject({
      doi: '10.1000/example',
      publicationType: { raw: 'case report', value: 'case_report' },
    });
  });

  it('updates normalized observed values without deleting raw, status, or correction metadata', () => {
    const original = {
      raw: 'case-report',
      sourceStatus: 'stated',
      value: 'case_report',
      correctionIds: ['correction-1'],
    };
    expect(updateObservedValue(original, 'cohort_study')).toEqual({
      raw: 'case-report',
      sourceStatus: 'stated',
      value: 'cohort_study',
      correctionIds: ['correction-1'],
    });
  });

  it.each([
    ['PRESENT', 'present'],
    ['EXCLUDED', 'absent'],
    ['NOT_REPORTED', 'not-reported'],
    ['NOT_APPLICABLE', 'not-applicable'],
    ['INDETERMINATE', 'unresolved'],
  ])('represents %s as the explicit %s state', (status) => {
    const next = setAssessmentStatus(assessment(), status);
    expect(next.curationStatus).toBe('CURATED');
    expect(next.assessmentStatus).toBe(status);
    expect(next.evidence).toEqual(assessment().evidence);
    if (!['PRESENT', 'EXCLUDED'].includes(status)) expect(next.findings).toEqual([]);
  });

  it('preserves uncurated as a separate workflow state', () => {
    const next = setAssessmentStatus(assessment(), null);
    expect(next).toMatchObject({ curationStatus: 'UNCURATED', assessmentStatus: null });
    expect(next.findings).toEqual([]);
  });

  it('does not create an invalid positive assessment without a mapped finding', () => {
    const untouched = assessment({
      curationStatus: 'UNCURATED',
      assessmentStatus: null,
      findings: [],
    });

    expect(setAssessmentStatus(untouched, 'PRESENT')).toEqual(untouched);
    expect(setAssessmentStatus(untouched, 'EXCLUDED')).toEqual(untouched);
  });

  it.each([
    ['none', []],
    ['bilateral', [{ id: 'HP:0012832', label: 'Bilateral' }]],
    ['unilateral', [{ id: 'HP:0012833', label: 'Unilateral' }]],
    ['unilateral-left', unilateralLeft],
    [
      'unilateral-right',
      [
        { id: 'HP:0012833', label: 'Unilateral' },
        { id: 'HP:0012834', label: 'Right' },
      ],
    ],
  ])('round-trips compound laterality %s with the exact modifier set', (value, modifiers) => {
    const next = setLaterality(assessment(), value);
    expect(next.findings[0].modifiers).toEqual(modifiers);
    expect(getLaterality(next)).toBe(value);
    expect(next.findings[0].sourceTerm).toEqual(assessment().findings[0].sourceTerm);
    expect(next.evidence).toEqual(assessment().evidence);
  });

  it('counts all explicit clinical states as curated and leaves untouched questions incomplete', () => {
    expect(
      assessmentCompleteness([
        assessment(),
        assessment({ curationStatus: 'CURATED', assessmentStatus: 'NOT_REPORTED' }),
        assessment({ curationStatus: 'UNCURATED', assessmentStatus: null }),
      ])
    ).toEqual({ filled: 2, total: 3 });
  });

  it('builds correction pointers with the active value and chain head intact', () => {
    const targets = correctionTargets({
      observationId: 'report/1',
      publication: {
        sourceKey: {
          raw: 'source',
          sourceStatus: 'stated',
          value: 'normalized',
          correctionIds: ['correction-1'],
        },
      },
    });
    expect(targets).toEqual([
      {
        path: 'publication.sourceKey',
        jsonPointer: '/observationsById/report~11/publication/sourceKey/value',
        storedValue: 'normalized',
        value: 'normalized',
        correctionIds: ['correction-1'],
        supersedesCorrectionId: null,
        chainValid: true,
      },
    ]);
  });

  it('derives a superseding correction preimage from the active chain head', () => {
    const observation = {
      observationId: 'report-1',
      variant: {
        reported: {
          raw: 'c.1A>G',
          sourceStatus: 'stated',
          value: 'original',
          correctionIds: ['one', 'two'],
        },
      },
    };
    const pointer = '/observationsById/report-1/variant/reported/value';
    const [target] = correctionTargets(observation, [
      {
        correctionId: 'two',
        jsonPointer: pointer,
        preimage: 'first',
        postimage: 'second',
        supersedesCorrectionId: 'one',
      },
      {
        correctionId: 'one',
        jsonPointer: pointer,
        preimage: 'original',
        postimage: 'first',
        supersedesCorrectionId: null,
      },
    ]);

    expect(target).toMatchObject({
      storedValue: 'original',
      value: 'second',
      supersedesCorrectionId: 'two',
      chainValid: true,
    });
  });
});
