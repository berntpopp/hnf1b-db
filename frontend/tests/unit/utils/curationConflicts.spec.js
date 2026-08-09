import { describe, expect, it } from 'vitest';

import {
  conflictCandidates,
  projectionSummary,
  threeWayObservationMerge,
} from '@/utils/curationAdapters';

const observations = [
  {
    observationId: 'report-1',
    identifiers: { reportId: 'RPT-1', sex: { raw: 'M', value: 'MALE' } },
    publication: { pmid: '123', doi: '10.1/a' },
    sourceReview: { reviewerDisplayLabel: 'Reviewer A', reviewedOn: '2024-02-03' },
  },
  {
    observationId: 'report-2',
    identifiers: { reportId: 'RPT-2', sex: { raw: 'F', value: 'FEMALE' } },
    publication: { pmid: '456' },
    sourceReview: { reviewerDisplayLabel: 'Reviewer B', reviewedOn: '2025-02-03' },
  },
];

describe('projection and conflict adapters', () => {
  it('builds evidence-rich candidates for a subject conflict without exposing email fields', () => {
    expect(conflictCandidates({ conflictKey: 'subject:sex' }, observations)).toEqual([
      {
        observationId: 'report-1',
        reportId: 'RPT-1',
        publication: 'PMID:123 · DOI:10.1/a',
        reviewedOn: '2024-02-03',
        reviewer: 'Reviewer A',
        raw: 'M',
        value: 'MALE',
        evidence: [],
      },
      {
        observationId: 'report-2',
        reportId: 'RPT-2',
        publication: 'PMID:456',
        reviewedOn: '2025-02-03',
        reviewer: 'Reviewer B',
        raw: 'F',
        value: 'FEMALE',
        evidence: [],
      },
    ]);
  });

  it('summarizes deterministic projection output for preview', () => {
    expect(
      projectionSummary({
        phenopacket: {
          subject: { id: '317', sex: 'MALE' },
          phenotypicFeatures: [{ type: { id: 'HP:0000107' } }],
          interpretations: [{ id: 'interpretation-1' }],
          metaData: { externalReferences: [{ id: 'PMID:123' }, { id: 'DOI:10.1/a' }] },
        },
        outputDigest: 'sha256:output',
        issues: [{ conflictKey: 'subject:sex' }],
      })
    ).toEqual({
      subjectId: '317',
      sex: 'MALE',
      phenotypeCount: 1,
      variantCount: 1,
      references: ['PMID:123', 'DOI:10.1/a'],
      conflictCount: 1,
      outputDigest: 'sha256:output',
    });
  });

  it('builds candidates for descriptor-scoped classification conflicts', () => {
    const variantObservations = observations.map((observation, index) => ({
      ...observation,
      variant: { normalized: { id: 'ga4gh:VA.abc' } },
      classification: {
        contribution: {
          raw: index ? 'risk' : 'causal',
          value: index ? 'CONTRIBUTORY' : 'CAUSATIVE',
        },
        verdict: { raw: index ? 'LP' : 'P', value: index ? 'LIKELY_PATHOGENIC' : 'PATHOGENIC' },
      },
    }));

    expect(
      conflictCandidates(
        { conflictKey: 'variant:ga4gh:VA.abc:contribution' },
        variantObservations
      ).map(({ raw, value }) => ({ raw, value }))
    ).toEqual([
      { raw: 'causal', value: 'CAUSATIVE' },
      { raw: 'risk', value: 'CONTRIBUTORY' },
    ]);
    expect(
      conflictCandidates({ conflictKey: 'variant:ga4gh:VA.abc:acmg' }, variantObservations)
    ).toHaveLength(2);
  });

  it('renders active corrected candidate values and phenotype evidence', () => {
    const phenotypeObservation = {
      ...observations[0],
      identifiers: {
        ...observations[0].identifiers,
        sex: { ...observations[0].identifiers.sex, sourceStatus: 'stated' },
      },
      phenotypes: [
        {
          assessmentId: 'renal-cyst',
          rawValue: 'yes',
          assessmentStatus: 'PRESENT',
          findings: [{ term: { id: 'HP:0000107' }, modifiers: [] }],
          evidence: [
            {
              reference: 'PMID:123',
              evidenceCode: { id: 'ECO:0006013', label: 'author statement' },
            },
          ],
        },
      ],
    };
    const pointer = '/observationsById/report-1/identifiers/sex/value';
    const candidates = conflictCandidates(
      { conflictKey: 'subject:sex' },
      [phenotypeObservation],
      [
        {
          correctionId: 'sex-correction',
          jsonPointer: pointer,
          preimage: 'MALE',
          postimage: 'FEMALE',
          supersedesCorrectionId: null,
        },
      ]
    );
    expect(candidates[0].value).toBe('FEMALE');

    expect(
      conflictCandidates({ conflictKey: 'phenotype:HP:0000107:polarity' }, [
        phenotypeObservation,
      ])[0].evidence
    ).toEqual([expect.objectContaining({ reference: 'PMID:123' })]);
  });

  it('three-way merges independent edits and identifies overlapping changes', () => {
    const base = { publication: { pmid: '1', doi: 'old' }, notes: { value: 'base' } };
    const local = { publication: { pmid: '2', doi: 'old' }, notes: { value: 'base' } };
    const server = { publication: { pmid: '1', doi: 'new' }, notes: { value: 'server' } };

    expect(threeWayObservationMerge(base, local, server)).toEqual({
      merged: { publication: { pmid: '2', doi: 'new' }, notes: { value: 'server' } },
      conflicts: [],
    });

    const conflicting = threeWayObservationMerge(
      base,
      { ...local, notes: { value: 'local' } },
      server
    );
    expect(conflicting.conflicts).toEqual([
      expect.objectContaining({
        path: 'notes.value',
        base: 'base',
        local: 'local',
        server: 'server',
      }),
    ]);
  });
});
