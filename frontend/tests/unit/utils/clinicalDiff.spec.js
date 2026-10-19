import { describe, expect, it } from 'vitest';
import { formatValueBrief, resolveClinicalSummaries } from '@/utils/clinicalDiff';

describe('clinicalDiff utility', () => {
  it('formats values briefly and sanitizes XSS content', () => {
    expect(formatValueBrief(null)).toBe('None');
    expect(formatValueBrief(undefined)).toBe('None');
    expect(formatValueBrief('<script>alert(1)</script>')).not.toContain('<script>');
    expect(formatValueBrief({ id: 'HP:0000107', label: 'Renal cyst' })).toBe(
      'Renal cyst (HP:0000107)'
    );
  });

  it('resolves phenotype addition, removal, and exclusion deltas', () => {
    const changes = [
      {
        section: 'Phenotypes',
        operation: 'changed',
        path: '/phenotypicFeatures/4/excluded',
        before: false,
        after: true,
      },
      {
        section: 'Phenotypes',
        operation: 'added',
        path: '/phenotypicFeatures/5',
        before: null,
        after: { type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: false },
      },
      {
        section: 'Phenotypes',
        operation: 'removed',
        path: '/phenotypicFeatures/1',
        before: { type: { id: 'HP:0001250', label: 'Seizure' } },
        after: null,
      },
    ];

    const baseline = {
      content: {
        phenotypicFeatures: [
          {},
          { type: { id: 'HP:0001250', label: 'Seizure' } },
          {},
          {},
          { type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: false },
        ],
      },
    };

    const summaries = resolveClinicalSummaries(changes, baseline, null);
    const phenoCat = summaries.find((c) => c.id === 'phenotypes');

    expect(phenoCat).toBeDefined();
    expect(phenoCat.items).toHaveLength(3);
    expect(phenoCat.items[0].text).toBe('HP:0000107 — Renal cyst (Present -> Excluded)');
    expect(phenoCat.items[1].text).toBe('Added: Renal cyst (HP:0000107)');
    expect(phenoCat.items[2].text).toBe('Removed: Seizure (HP:0001250)');
  });

  it('resolves variant, ACMG classification, and interpretation status deltas', () => {
    const changes = [
      {
        section: 'Variants/Interpretations',
        operation: 'changed',
        path: '/interpretations/0/diagnosis/genomicInterpretations/0/variantInterpretation/acmgPathogenicityClassification',
        before: 'UNCERTAIN_SIGNIFICANCE',
        after: 'PATHOGENIC',
      },
      {
        section: 'Variants/Interpretations',
        operation: 'changed',
        path: '/interpretations/0/diagnosis/genomicInterpretations/0/interpretationStatus',
        before: 'CANDIDATE',
        after: 'CAUSATIVE',
      },
    ];

    const candidate = {
      content: {
        interpretations: [
          {
            diagnosis: {
              genomicInterpretations: [
                {
                  variantInterpretation: {
                    variationDescriptor: {
                      id: 'var-1',
                      label: 'c.827G>A (p.Arg276Gln)',
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

    const summaries = resolveClinicalSummaries(changes, null, candidate);
    const varCat = summaries.find((c) => c.id === 'variants');

    expect(varCat).toBeDefined();
    expect(varCat.items).toHaveLength(2);
    expect(varCat.items[0].text).toContain('HNF1B c.827G>A (p.Arg276Gln) — ACMG classification');
    expect(varCat.items[0].text).toContain('UNCERTAIN_SIGNIFICANCE -> PATHOGENIC');
    expect(varCat.items[1].text).toContain('Interpretation status: CANDIDATE -> CAUSATIVE');
  });

  it('resolves subject and disease onset deltas', () => {
    const changes = [
      {
        section: 'Subject',
        operation: 'changed',
        path: '/subject/sex',
        before: 'UNKNOWN_SEX',
        after: 'FEMALE',
      },
      {
        section: 'Diseases',
        operation: 'changed',
        path: '/diseases/0/onset/age/iso8601duration',
        before: 'P12Y',
        after: 'P18Y',
      },
    ];

    const candidate = {
      content: {
        diseases: [{ term: { id: 'OMIM:137920', label: 'RCAD' } }],
      },
    };

    const summaries = resolveClinicalSummaries(changes, null, candidate);
    const subjCat = summaries.find((c) => c.id === 'subject');

    expect(subjCat).toBeDefined();
    expect(subjCat.items).toHaveLength(2);
    expect(subjCat.items[0].text).toBe('Subject sex: UNKNOWN_SEX -> FEMALE');
    expect(subjCat.items[1].text).toContain('Disease onset: RCAD');
  });

  it('resolves removed items from baseline, nested genomicInterpretation index, and nested field edits', () => {
    const baseline = {
      content: {
        phenotypicFeatures: [
          { type: { id: 'HP:0000107', label: 'Renal cyst' } },
          { type: { id: 'HP:0000819', label: 'Diabetes mellitus' } },
        ],
      },
    };
    const candidate = {
      content: {
        phenotypicFeatures: [{ type: { id: 'HP:0000819', label: 'Diabetes mellitus' } }],
        interpretations: [
          {
            diagnosis: {
              genomicInterpretations: [
                {
                  variantInterpretation: {
                    variationDescriptor: { label: 'c.100G>A', geneContext: { value: 'HNF1B' } },
                  },
                },
                {
                  variantInterpretation: {
                    variationDescriptor: { label: 'c.544+1G>A', geneContext: { value: 'HNF1B' } },
                  },
                },
              ],
            },
          },
        ],
      },
    };
    const changes = [
      {
        section: 'Phenotypes',
        operation: 'removed',
        path: '/phenotypicFeatures/0',
        before: null,
        after: null,
      },
      {
        section: 'Phenotypes',
        operation: 'added',
        path: '/phenotypicFeatures/0/onset',
        before: null,
        after: { age: { iso8601duration: 'P10Y' } },
      },
      {
        section: 'Variants/Interpretations',
        operation: 'changed',
        path: '/interpretations/0/diagnosis/genomicInterpretations/1/variantInterpretation/acmgPathogenicityClassification',
        before: 'LIKELY_PATHOGENIC',
        after: 'PATHOGENIC',
      },
    ];

    const summaries = resolveClinicalSummaries(changes, baseline, candidate);
    const phenoCat = summaries.find((c) => c.id === 'phenotypes');
    const varCat = summaries.find((c) => c.id === 'variants');

    expect(phenoCat.items[0].text).toBe('Removed: Renal cyst (HP:0000107)');
    expect(phenoCat.items[1].text).toBe(
      'HP:0000819 — Diabetes mellitus: onset changed (None -> P10Y)'
    );
    expect(varCat.items[0].text).toContain('HNF1B c.544+1G>A — ACMG classification');
  });
});
