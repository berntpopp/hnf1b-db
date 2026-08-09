/**
 * Shared field registry for the curation console (curation console design
 * spec §2.1, §3; plan Task 3 seeds it, Tasks 4/5/6/8 append their own field
 * entries to CURATION_FIELDS in later commits).
 *
 * ── Central semantic (read this before touching this file) ──────────────
 * **Absence != `not_reported`.** Absent means "not yet curated" -- the
 * curator hasn't touched the field (value is `undefined`/`null`/`''`/empty
 * array). `not_reported` is an ordinary *selected* value meaning "the source
 * publication is silent about this" -- it is one of the options in several of
 * the six curation vocabularies (e.g. `familyHistory`, `detectionMethod`) but
 * deliberately NOT in `cohort_values` (the sheet states cohort for all 939
 * rows, so an absent cohort really does mean "not yet curated", never
 * "not_reported"). A field holding the string `'not_reported'` counts as
 * FILLED for completeness purposes, exactly like any other selected value.
 *
 * NEVER special-case the literal string 'not_reported' anywhere in this file
 * or in a field's `isFilled`. Collapsing "has a value" and "has no value"
 * into the same bucket is exactly the defect the completeness rail exists to
 * make visible.
 */

export const CURATION_SECTIONS = [
  { id: 'case', label: 'Case' },
  { id: 'variant', label: 'Variant' },
  { id: 'classification', label: 'Classification' },
  { id: 'phenotypes', label: 'Phenotypes' },
  { id: 'age', label: 'Age & Onset' },
  { id: 'provenance', label: 'Provenance & Notes' },
];

/**
 * CURATION_FIELDS entries: { id, section, getValue(phenopacket) => value, isFilled?(value) => bool }
 *
 * - `id`: unique string, stable across commits (not currently used for
 *   lookups, but treat it as a public key -- other code may key off it later).
 * - `section`: must be one of CURATION_SECTIONS' ids, EXCEPT 'phenotypes'.
 *   The Phenotypes section's completeness is NOT driven by this registry --
 *   it's dynamic per-case (the set of phenotype features varies per record),
 *   and is computed by whoever owns that section (Task 7) and passed into
 *   CompletenessRail as the `phenotypesCompleteness` prop instead.
 * - `getValue(phenopacket)`: pure function, reads the field's current value
 *   out of a phenopacket. Must not mutate `phenopacket`.
 * - `isFilled(value)` (optional): overrides the default fill rule below for
 *   fields where "filled" isn't simply "has a non-empty value" (e.g. a field
 *   that is only meaningful once a sibling field is set). Do not use this to
 *   special-case 'not_reported' -- see the module docstring.
 *
 * Deliberately a plain mutable array, not frozen/sealed: later commits do
 * `CURATION_FIELDS.push(...)` (or splice/filter) to register their fields.
 */
import { VARIANT_TYPE_IDS } from '@/utils/soTerms';

export const CURATION_FIELDS = [];

// ── Task 4: Case section (design spec §3.1) ────────────────────────────────
// Cohort, Sex, IndividualIdentifier, Publication, PublicationType,
// FamilyHistory. Sex and Publication already had storage/controls before
// this task; they are registered here anyway so the Case section's
// completeness badge accounts for every one of its six dimensions, not just
// the four that are new.
CURATION_FIELDS.push(
  {
    id: 'cohort',
    section: 'case',
    getValue: (p) => p?.hnf1bCuration?.cohort,
  },
  {
    id: 'sex',
    // The form defaults `subject.sex` to the literal string 'UNKNOWN_SEX',
    // which is itself a legitimate GA4GH Sex enum member the curator can
    // deliberately select -- not a placeholder for "untouched". No custom
    // `isFilled` needed: the default rule already treats any non-empty
    // string, including 'UNKNOWN_SEX', as filled.
    section: 'case',
    getValue: (p) => p?.subject?.sex,
  },
  {
    id: 'individualIdentifiers',
    section: 'case',
    getValue: (p) => p?.subject?.alternateIds,
  },
  {
    id: 'publication',
    section: 'case',
    getValue: (p) => p?.metaData?.externalReferences,
    // A bare `{id: 'PMID:'}` (empty-PMID row mid-typing) must not count as
    // filled -- guard against it explicitly rather than relying on the
    // default non-empty-array rule, which would be fooled by it.
    isFilled: (refs) =>
      Array.isArray(refs) && refs.some((r) => r?.id?.startsWith('PMID:') && r.id !== 'PMID:'),
  },
  {
    id: 'publicationType',
    section: 'case',
    getValue: (p) => p?.hnf1bCuration?.publicationType,
  },
  {
    id: 'familyHistory',
    section: 'case',
    getValue: (p) => p?.hnf1bCuration?.familyHistory,
  }
);

// ── Task 5: Variant section (design spec §3.2) ──────────────────────────────
// VariantReported, VariantType, hg38, hg19, coordinates (hg19_INFO/
// hg38_INFO), dbVar ID, Varsome, DetecionMethod [sic, sheet's actual column
// name], Segregation, allelicState.
//
// `phenopacket.interpretations` is an array -- a case CAN have multiple
// variants (e.g. biallelic) -- but this registry is a fixed ~28-dimension
// completeness count, so it only tracks the primary/first variant. The
// design spec's "~28 dimensions" total (6 Case + 10 Variant + 5
// Classification + 2 Age + 5 Provenance = 28) only makes sense as a
// per-case, not per-variant-instance, count.
const firstVariationDescriptor = (p) =>
  p?.interpretations?.[0]?.diagnosis?.genomicInterpretations?.[0]?.variantInterpretation
    ?.variationDescriptor;

CURATION_FIELDS.push(
  {
    id: 'variantReported',
    section: 'variant',
    getValue: (p) => firstVariationDescriptor(p)?.description,
  },
  {
    id: 'variantType',
    section: 'variant',
    // One sheet column, two landing places: deletion/duplication are
    // structural and live on `structuralType`; SNV/indel are not and live on
    // `molecularConsequences`. See soTerms.js::STRUCTURAL_TYPE_IDS.
    getValue: (p) => {
      const descriptor = firstVariationDescriptor(p);
      return (
        descriptor?.structuralType ??
        (descriptor?.molecularConsequences || []).find((c) => VARIANT_TYPE_IDS.has(c.id))
      );
    },
  },
  {
    id: 'hg38',
    section: 'variant',
    // The sheet's hg38/hg19 columns are VCF-style dash notation, which the
    // corpus stores under syntax 'vcf' (864 records, none carrying a
    // `version`). hg38 is the untagged entry -- the one every existing
    // reader's `.find(e => e.syntax === 'vcf')` resolves to -- and hg19,
    // which has no corpus precedent, is tagged version 'GRCh37'.
    getValue: (p) =>
      firstVariationDescriptor(p)?.expressions?.find(
        (e) => e.syntax === 'vcf' && e.version !== 'GRCh37'
      )?.value,
  },
  {
    id: 'hg19',
    section: 'variant',
    getValue: (p) =>
      firstVariationDescriptor(p)?.expressions?.find(
        (e) => e.syntax === 'vcf' && e.version === 'GRCh37'
      )?.value,
  },
  {
    id: 'coordinates',
    section: 'variant',
    // Derived, read-only (design spec §3.2: hg19_INFO/hg38_INFO) -- the
    // console never writes this; filled iff the legacy `coordinates`
    // extension (already present on 440 records) is present.
    getValue: (p) =>
      firstVariationDescriptor(p)?.extensions?.find((e) => e.name === 'coordinates')?.value,
  },
  {
    id: 'dbVarId',
    section: 'variant',
    getValue: (p) => firstVariationDescriptor(p)?.xrefs,
  },
  {
    id: 'varsome',
    section: 'variant',
    // The one canonical hgvs.c entry -- no versioning needed here, unlike
    // hg38/hg19.
    getValue: (p) =>
      firstVariationDescriptor(p)?.expressions?.find((e) => e.syntax === 'hgvs.c')?.value,
  },
  {
    id: 'detectionMethod',
    // Case-level (design spec §3.2), unlike the other nine variant fields --
    // one publication reports one detection method for the case, not one
    // per variant.
    section: 'variant',
    getValue: (p) => p?.hnf1bCuration?.detectionMethod,
  },
  {
    id: 'segregation',
    section: 'variant',
    getValue: (p) =>
      firstVariationDescriptor(p)?.extensions?.find((e) => e.name === 'segregation')?.value?.origin,
  },
  {
    id: 'allelicState',
    section: 'variant',
    getValue: (p) => firstVariationDescriptor(p)?.allelicState,
  }
);

// ── Task 6: Classification section (design spec §3.3) ──────────────────────
// verdict_classification, criteria_classification, system_classification,
// date_classification, comment_classification.
//
// `verdict` and `criteria` both read off the SAME primary/first variant
// convention Task 5's fields use (interpretations[0]) -- but unlike
// firstVariationDescriptor (variantInterpretation.variationDescriptor),
// `interpretationStatus` is a SIBLING of `variantInterpretation` on the
// genomicInterpretation itself (ADR 0003 D1: this is deliberate, not a typo --
// the console never writes the GA4GH-conformant
// `variantInterpretation.acmgPathogenicityClassification`), and
// `classification_criteria` lives on `variantInterpretation.extensions`
// (NOT `variationDescriptor.extensions`, where Task 5's `segregation`/
// `coordinates` extensions live) -- so this section needs its own accessor,
// not firstVariationDescriptor.
const firstGenomicInterpretation = (p) =>
  p?.interpretations?.[0]?.diagnosis?.genomicInterpretations?.[0];

CURATION_FIELDS.push(
  {
    id: 'verdict',
    section: 'classification',
    getValue: (p) => firstGenomicInterpretation(p)?.interpretationStatus,
    // Unlike `sex`'s 'UNKNOWN_SEX' default (a real, selectable GA4GH enum
    // member), the string 'UNKNOWN' is not a member of the
    // `interpretation-status` vocabulary at all -- Task 5's
    // createInterpretation/saveDetailedVariant seed every new variant with
    // it before the curator has made any verdict choice. Treating it as
    // filled would mark the Classification section's verdict complete the
    // instant a variant is added, before a verdict was ever entered.
    isFilled: (value) => !!value && value !== 'UNKNOWN',
  },
  {
    id: 'criteria',
    section: 'classification',
    getValue: (p) =>
      firstGenomicInterpretation(p)?.variantInterpretation?.extensions?.find(
        (e) => e.name === 'classification_criteria'
      )?.value?.criteria,
  },
  {
    id: 'classificationSystem',
    section: 'classification',
    getValue: (p) => p?.hnf1bCuration?.classificationSystem,
  },
  {
    id: 'classificationDate',
    section: 'classification',
    getValue: (p) => p?.hnf1bCuration?.classificationDate,
  },
  {
    id: 'classificationComment',
    section: 'classification',
    getValue: (p) => p?.hnf1bCuration?.classificationComment,
  }
);

// ── Task 8: Age & onset section (design spec §3.5) ──────────────────────────
// AgeOnset -> diseases[0].onset, AgeReported -> subject.timeAtLastEncounter.
// Both are GA4GH TimeElement objects (congenital OntologyClass / ISO-8601 age
// / gestational age -- see TimeElementPicker.vue). Unlike the vocabulary-
// backed fields Tasks 4-6 registered, a TimeElement has no `not_reported`
// concept -- GA4GH doesn't model "the source is silent about onset" as a
// selectable value the way `familyHistory`/`detectionMethod` do -- so these
// use the plain default fill rule (non-empty object = filled) with no
// custom `isFilled`.
CURATION_FIELDS.push(
  {
    id: 'ageOnset',
    section: 'age',
    getValue: (p) => p?.diseases?.[0]?.onset,
  },
  {
    id: 'ageReported',
    section: 'age',
    getValue: (p) => p?.subject?.timeAtLastEncounter,
  }
);

// ── Task 8: Provenance & notes section (design spec §3.6) ───────────────────
// ReviewBy -> hnf1bCuration.curatedBy (+ metaData.reviewer, stamped
// alongside it but not separately registered here), ReviewDate ->
// curatedAt, Comment/Problematic/DupCheck -> the three free-text fields.
// curatedBy/curatedAt are auto-stamped by PhenopacketCreateEdit.vue's
// stampCuration() -- there is deliberately NO curator-facing input control
// for either (see ProvenanceSection.vue's module doc, the programme's
// no-reviewer-input-control non-negotiable) -- so they read filled as soon
// as the form mounts, not only after an explicit curator action.
CURATION_FIELDS.push(
  {
    id: 'curatedBy',
    section: 'provenance',
    getValue: (p) => p?.hnf1bCuration?.curatedBy,
  },
  {
    id: 'curatedAt',
    section: 'provenance',
    getValue: (p) => p?.hnf1bCuration?.curatedAt,
  },
  {
    id: 'caseComment',
    section: 'provenance',
    getValue: (p) => p?.hnf1bCuration?.caseComment,
  },
  {
    id: 'problematic',
    section: 'provenance',
    getValue: (p) => p?.hnf1bCuration?.problematic,
  },
  {
    id: 'duplicateCheck',
    section: 'provenance',
    getValue: (p) => p?.hnf1bCuration?.duplicateCheck,
  }
);

/**
 * Default fill rule (used when a field does not supply its own `isFilled`):
 * arrays are filled iff non-empty; everything else is filled iff
 * `value !== undefined && value !== null && value !== ''`.
 *
 * The literal string 'not_reported' passes this rule like any other
 * non-empty value -- that is the point, not an oversight.
 */
function defaultIsFilled(value) {
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  return value !== undefined && value !== null && value !== '';
}

/**
 * Whether a single registered field counts as filled for a given phenopacket.
 * @param {{getValue: Function, isFilled?: Function}} field
 * @param {Object} phenopacket
 * @returns {boolean}
 */
export function isFieldFilled(field, phenopacket) {
  const value = field.getValue(phenopacket);
  if (typeof field.isFilled === 'function') {
    return field.isFilled(value);
  }
  return defaultIsFilled(value);
}

/**
 * Completeness for one section of CURATION_SECTIONS, computed from every
 * CURATION_FIELDS entry registered against that section id.
 *
 * NOT valid for `sectionId === 'phenotypes'` -- that section has no entries
 * in CURATION_FIELDS by design (see the field docs above) and will always
 * report {filled: 0, total: 0} here. Callers must source the Phenotypes
 * section's completeness elsewhere (see CompletenessRail.vue).
 *
 * @param {Object} phenopacket
 * @param {string} sectionId
 * @returns {{filled: number, total: number}}
 */
export function computeSectionCompleteness(phenopacket, sectionId) {
  const fields = CURATION_FIELDS.filter((field) => field.section === sectionId);
  const total = fields.length;
  const filled = fields.reduce(
    (count, field) => count + (isFieldFilled(field, phenopacket) ? 1 : 0),
    0
  );
  return { filled, total };
}
