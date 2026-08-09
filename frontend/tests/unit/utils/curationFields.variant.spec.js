/**
 * Unit tests for the Variant section's CURATION_FIELDS entries (curation
 * console plan Task 5; design spec §3.2: VariantReported, VariantType, hg38,
 * hg19, coordinates (hg19_INFO/hg38_INFO), dbVar ID, Varsome, DetecionMethod
 * [sic], Segregation, allelicState).
 *
 * Like curationFields.spec.js (Task 4's Case section suite), these exercise
 * the actual registered entries to reinforce the programme's central
 * semantic for this section: **absence != `not_reported`**. `segregation`
 * and `detectionMethod` both admit `not_reported` in their vocabularies
 * (backend/alembic/versions/a1c4e7f20b93_add_curation_vocabularies.py) --
 * this suite proves the literal string counts as filled while absence does
 * not, for both.
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

/** Build a phenopacket carrying a single interpretation whose variationDescriptor is `descriptor`. */
function withDescriptor(descriptor) {
  return {
    interpretations: [
      {
        diagnosis: {
          genomicInterpretations: [
            {
              variantInterpretation: {
                variationDescriptor: descriptor,
              },
            },
          ],
        },
      },
    ],
  };
}

describe('CURATION_FIELDS — variant section (Task 5)', () => {
  it('registers exactly the ten variant-section fields', () => {
    const variantFieldIds = CURATION_FIELDS.filter((f) => f.section === 'variant').map((f) => f.id);
    expect(variantFieldIds.sort()).toEqual(
      [
        'variantReported',
        'variantType',
        'hg38',
        'hg19',
        'coordinates',
        'dbVarId',
        'varsome',
        'detectionMethod',
        'segregation',
        'allelicState',
      ].sort()
    );
  });

  describe('variantReported', () => {
    it('reads variationDescriptor.description off the first/primary variant', () => {
      const field = fieldById('variantReported');
      expect(field.getValue(withDescriptor({ description: 'TCF2, c.182T>G, V61G' }))).toBe(
        'TCF2, c.182T>G, V61G'
      );
    });

    it('is filled when set and not filled when absent', () => {
      const field = fieldById('variantReported');
      expect(isFieldFilled(field, withDescriptor({ description: 'TCF2, c.182T>G' }))).toBe(true);
      expect(isFieldFilled(field, withDescriptor({}))).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });
  });

  describe('variantType', () => {
    it('reads variationDescriptor.structuralType as an SO term object', () => {
      const field = fieldById('variantType');
      const structuralType = { id: 'SO:0000159', label: 'deletion' };
      expect(field.getValue(withDescriptor({ structuralType }))).toEqual(structuralType);
    });

    it('reads SNV/indel from molecularConsequences, where the corpus keeps them', () => {
      // The corpus partition is exact: 440 deletion/duplication on
      // structuralType, 424 SNV/indel on molecularConsequences.
      const field = fieldById('variantType');
      const snv = { id: 'SO:0001483', label: 'SNV' };
      expect(field.getValue(withDescriptor({ molecularConsequences: [snv] }))).toEqual(snv);
    });

    it('ignores a VEP consequence term that is not a variant type', () => {
      const field = fieldById('variantType');
      const vep = { id: 'SO:0001583', label: 'missense_variant' };
      expect(field.getValue(withDescriptor({ molecularConsequences: [vep] }))).toBeUndefined();
    });

    it('is filled when set and not filled when absent', () => {
      const field = fieldById('variantType');
      expect(
        isFieldFilled(
          field,
          withDescriptor({ structuralType: { id: 'SO:1000035', label: 'duplication' } })
        )
      ).toBe(true);
      expect(
        isFieldFilled(
          field,
          withDescriptor({ molecularConsequences: [{ id: 'SO:1000032', label: 'indel' }] })
        )
      ).toBe(true);
      expect(isFieldFilled(field, withDescriptor({}))).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });
  });

  describe('hg38 / hg19 — both use syntax vcf, hg19 disambiguated by version', () => {
    // The sheet's hg38/hg19 columns are VCF-style dash notation, which the
    // corpus stores under syntax 'vcf' with no version key. hg38 is therefore
    // the untagged entry -- the one existing readers resolve to -- and hg19,
    // which has no corpus precedent, carries version 'GRCh37'.
    const expressions = [
      { syntax: 'vcf', value: 'chr17-37739541-G-A' },
      { syntax: 'vcf', value: 'chr17-36099532-G-A', version: 'GRCh37' },
    ];

    it('hg38 reads the untagged vcf entry, as migrated records store it', () => {
      const field = fieldById('hg38');
      expect(field.getValue(withDescriptor({ expressions }))).toBe('chr17-37739541-G-A');
    });

    it('hg19 reads the GRCh37-tagged entry specifically, independent of hg38', () => {
      const field = fieldById('hg19');
      expect(field.getValue(withDescriptor({ expressions }))).toBe('chr17-36099532-G-A');
    });

    it('hg38 and hg19 are independently trackable as filled/unfilled', () => {
      const hg38Field = fieldById('hg38');
      const hg19Field = fieldById('hg19');
      // Only hg38 present.
      const onlyHg38 = withDescriptor({ expressions: [expressions[0]] });
      expect(isFieldFilled(hg38Field, onlyHg38)).toBe(true);
      expect(isFieldFilled(hg19Field, onlyHg38)).toBe(false);
    });

    it('both absent when expressions is absent entirely', () => {
      expect(isFieldFilled(fieldById('hg38'), withDescriptor({}))).toBe(false);
      expect(isFieldFilled(fieldById('hg19'), withDescriptor({}))).toBe(false);
    });
  });

  describe('coordinates — derived, read-only', () => {
    it('reads the coordinates extension value', () => {
      const field = fieldById('coordinates');
      const coordinatesValue = {
        assembly: 'GRCh38/hg38',
        chromosome: '17',
        start: 37739589,
        end: 37739589,
        length: 1,
      };
      const extensions = [{ name: 'coordinates', value: coordinatesValue }];
      expect(field.getValue(withDescriptor({ extensions }))).toEqual(coordinatesValue);
    });

    it('is filled iff the coordinates extension is present', () => {
      const field = fieldById('coordinates');
      expect(
        isFieldFilled(
          field,
          withDescriptor({ extensions: [{ name: 'coordinates', value: { chromosome: '17' } }] })
        )
      ).toBe(true);
      expect(
        isFieldFilled(field, withDescriptor({ extensions: [{ name: 'zygosity', value: 'het' }] }))
      ).toBe(false);
      expect(isFieldFilled(field, withDescriptor({}))).toBe(false);
    });
  });

  describe('dbVarId', () => {
    it('reads variationDescriptor.xrefs', () => {
      const field = fieldById('dbVarId');
      expect(field.getValue(withDescriptor({ xrefs: ['dbVar:nssv1184554'] }))).toEqual([
        'dbVar:nssv1184554',
      ]);
    });

    it('is filled iff the array is non-empty (default array rule)', () => {
      const field = fieldById('dbVarId');
      expect(isFieldFilled(field, withDescriptor({ xrefs: ['dbVar:nssv1184554'] }))).toBe(true);
      expect(isFieldFilled(field, withDescriptor({ xrefs: [] }))).toBe(false);
      expect(isFieldFilled(field, withDescriptor({}))).toBe(false);
    });
  });

  describe('varsome', () => {
    it('reads the canonical hgvs.c expression entry', () => {
      const field = fieldById('varsome');
      const expressions = [{ syntax: 'hgvs.c', value: 'NM_000458.4:c.395A>G' }];
      expect(field.getValue(withDescriptor({ expressions }))).toBe('NM_000458.4:c.395A>G');
    });

    it('is filled when set and not filled when absent', () => {
      const field = fieldById('varsome');
      expect(
        isFieldFilled(
          field,
          withDescriptor({ expressions: [{ syntax: 'hgvs.c', value: 'NM_000458.4:c.395A>G' }] })
        )
      ).toBe(true);
      expect(isFieldFilled(field, withDescriptor({}))).toBe(false);
    });
  });

  describe('detectionMethod — case-level, not per-variant', () => {
    it('reads hnf1bCuration.detectionMethod, not the variant descriptor', () => {
      const field = fieldById('detectionMethod');
      expect(field.getValue({ hnf1bCuration: { detectionMethod: 'ngs' } })).toBe('ngs');
    });

    it('counts the literal string "not_reported" as FILLED, and absence as NOT filled', () => {
      const field = fieldById('detectionMethod');
      expect(isFieldFilled(field, { hnf1bCuration: { detectionMethod: 'not_reported' } })).toBe(
        true
      );
      expect(isFieldFilled(field, { hnf1bCuration: {} })).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });

    it('never conflates an explicit not_reported value with an absent field', () => {
      const field = fieldById('detectionMethod');
      const filled = isFieldFilled(field, { hnf1bCuration: { detectionMethod: 'not_reported' } });
      const absent = isFieldFilled(field, {});
      expect(filled).not.toBe(absent);
    });
  });

  describe('segregation — central semantic: absence != not_reported', () => {
    it('reads extensions[segregation].value.origin off the first/primary variant', () => {
      const field = fieldById('segregation');
      const extensions = [{ name: 'segregation', value: { origin: 'de_novo' } }];
      expect(field.getValue(withDescriptor({ extensions }))).toBe('de_novo');
    });

    it('counts the literal string "not_reported" as FILLED', () => {
      const field = fieldById('segregation');
      const extensions = [{ name: 'segregation', value: { origin: 'not_reported' } }];
      expect(isFieldFilled(field, withDescriptor({ extensions }))).toBe(true);
    });

    it('counts an absent segregation extension as NOT filled', () => {
      const field = fieldById('segregation');
      expect(isFieldFilled(field, withDescriptor({}))).toBe(false);
      expect(isFieldFilled(field, withDescriptor({ extensions: [] }))).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });

    it('never conflates an explicit not_reported value with an absent field', () => {
      const field = fieldById('segregation');
      const filled = isFieldFilled(
        field,
        withDescriptor({ extensions: [{ name: 'segregation', value: { origin: 'not_reported' } }] })
      );
      const absent = isFieldFilled(field, withDescriptor({}));
      expect(filled).not.toBe(absent);
    });
  });

  describe('allelicState', () => {
    it('reads variationDescriptor.allelicState as a GENO term object', () => {
      const field = fieldById('allelicState');
      const allelicState = { id: 'GENO:0000135', label: 'heterozygous' };
      expect(field.getValue(withDescriptor({ allelicState }))).toEqual(allelicState);
    });

    it('is filled when set and not filled when absent', () => {
      const field = fieldById('allelicState');
      expect(
        isFieldFilled(
          field,
          withDescriptor({ allelicState: { id: 'GENO:0000135', label: 'heterozygous' } })
        )
      ).toBe(true);
      expect(isFieldFilled(field, withDescriptor({}))).toBe(false);
      expect(isFieldFilled(field, {})).toBe(false);
    });
  });

  it('only ever tracks the primary/first variant, ignoring a second interpretation entirely', () => {
    const field = fieldById('variantReported');
    const phenopacket = {
      interpretations: [
        {
          diagnosis: {
            genomicInterpretations: [
              { variantInterpretation: { variationDescriptor: { description: 'first variant' } } },
            ],
          },
        },
        {
          diagnosis: {
            genomicInterpretations: [
              {
                variantInterpretation: {
                  variationDescriptor: { description: 'second variant (biallelic partner)' },
                },
              },
            ],
          },
        },
      ],
    };
    expect(field.getValue(phenopacket)).toBe('first variant');
  });
});
