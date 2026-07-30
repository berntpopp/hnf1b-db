# Curation Data Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the create/edit form from writing malformed phenopackets, and add the storage contract (`hnf1bCuration` block, `segregation` extension, laterality modifiers, four controlled vocabularies) that the curation console will write into.

**Architecture:** Two phases. Phase 1 is frontend-only defect repair plus one dead-module deletion — no schema, no data, no backend behaviour change. Phase 2 adds reference tables, vocabulary endpoints, a schema declaration for a namespaced `hnf1bCuration` block, and an async domain validator on the REST write path. Everything Phase 2 stores lives inside the phenopacket JSONB, so it inherits revisioning, audit, draft/publish isolation and optimistic locking from the existing architecture at no cost.

**Tech Stack:** Vue 3 (Options API + `<script setup>`), Vuetify 3, Vitest; FastAPI, SQLAlchemy 2 async, Alembic, PostgreSQL 15, pytest; FastMCP sidecar.

**Spec:** [`docs/superpowers/specs/2026-07-30-curation-data-model-design.md`](../specs/2026-07-30-curation-data-model-design.md)
**ADR:** [`docs/adr/0003-ga4gh-conformance-debt.md`](../../adr/0003-ga4gh-conformance-debt.md)

## Global Constraints

- **Additive only, precisely.** No task may rewrite `phenopackets.phenopacket` or `phenopacket_revisions.content_jsonb` for any existing record. Additive *reference-data* changes are expected and allowed (Task 5 creates vocabulary tables; Task 7 adds a column to `hpo_terms_lookup` and sets it for six rows). The Done criteria prove the distinction with content hashes, not timestamps.
- **Verified against live data before planning:** all 771 laterality modifiers in the corpus sit on the five terms in Task 7's policy (`HP:0000107` 287, `HP:0033132` 173, `HP:0000003` 158, `HP:0000089` 112, `HP:0000079` 41), and `HP:0010935` appears in **zero** records despite `backend/migration/phenopackets/hpo_mapper.py:143` referencing it. No legacy record is rejected by the Task 9 validator. Re-run the query in the Done criteria if the corpus has changed since 2026-07-30.
- **Do not "fix" the conformance debt.** ACMG stays in `genomicInterpretations[].interpretationStatus`. `classification_criteria` stays on `variantInterpretation.extensions`. `timeAtLastEncounter` keeps the flat `{"iso8601duration": …}` shape. New extension values are objects, matching the existing five. These are deliberate (ADR 0003); reverting them breaks the sequencing.
- **Validation errors are HTTP 400**, matching `backend/app/phenopackets/routers/crud.py:448` — not 422.
- **Reference tables use `sort_order`**, not `display_order`. All are raw-SQL managed and must be added to `backend/alembic/env.py::include_object`.
- **Vocabulary responses are wrapped in `{"data": [...]}`.** New endpoints use item shape `{value, label, description}`.
- **Any task that adds or changes an API route MUST refresh the OpenAPI snapshot in the same commit.** `backend/tests/test_openapi_contract.py` asserts `mcp/contract/openapi.snapshot.json` equals the live `app.openapi()`, so a new route fails the backend suite immediately. Refresh with `cd backend && uv run python scripts/dump_openapi.py`. Note `make contract` in `mcp/` does **not** regenerate the snapshot — it *reads* it (`mcp/Makefile:15-16`) to produce `_generated_models.py`. Order is always: add route → `dump_openapi.py` → `cd mcp && make contract`. This affects Tasks 6, 7 and 10.
- Backend: run `cd backend && uv run ruff format` before every commit — CI runs `ruff format --check` as a separate step that local `make check` does not cover.
- Frontend: use `npm run lint:check`, never `npm run lint` (the latter applies `--fix` and fights prettier).
- Frontend dev server must run on port 3000 (`--port 3000 --strictPort`); it is the CORS-allowed origin.

---

# Phase 1 — Stop the corruption

## Task 1: Fix `moleculeContext`, `variation`, `impact` and `caddScore` (B1, B2, B7)

`VariantAnnotationForm.vue` writes three malformed things into every interpretation it creates: the VEP consequence string into `moleculeContext` (a GA4GH enum), a `{notation: …}` object into `variation` (which must be VRS), and `impact`/`caddScore` onto `VariantInterpretation` (which has no such fields).

The corpus already has the right home for consequence: `variationDescriptor.molecularConsequences`, an array of SO terms — `[{"id": "SO:0001483", "label": "SNV"}]` in 424 records. `moleculeContext` is `"genomic"` in those same 424.

`impact` and `caddScore` are derived VEP annotation, re-fetchable from `POST /api/v2/variants/annotate` at any time. They are dropped from the payload and kept in component state for display only.

**Files:**
- Modify: `frontend/src/components/VariantAnnotationForm.vue:242-286`
- Test: `frontend/tests/unit/components/VariantAnnotationForm.spec.js` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `createInterpretation(variantNotation: string, geneSymbol: string, annotationData?: {consequence?: string, consequenceSoId?: string, impact?: string, caddScore?: number}) → Interpretation`. Task 3 and the Phase 3 console rely on this shape.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/unit/components/VariantAnnotationForm.spec.js`:

```javascript
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import VariantAnnotationForm from '@/components/VariantAnnotationForm.vue';

const vuetify = createVuetify();

function mountForm() {
  return mount(VariantAnnotationForm, {
    props: { modelValue: [], subjectId: 'subject-1' },
    global: { plugins: [vuetify] },
  });
}

function descriptorOf(interpretation) {
  return interpretation.diagnosis.genomicInterpretations[0].variantInterpretation
    .variationDescriptor;
}

describe('VariantAnnotationForm payload shape', () => {
  it('sets moleculeContext to a GA4GH enum member, never a VEP consequence', () => {
    const wrapper = mountForm();
    const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B', {
      consequence: 'missense_variant',
      consequenceSoId: 'SO:0001583',
    });

    expect(descriptorOf(interp).moleculeContext).toBe('genomic');
  });

  it('records the VEP consequence as an SO term in molecularConsequences', () => {
    const wrapper = mountForm();
    const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B', {
      consequence: 'missense_variant',
      consequenceSoId: 'SO:0001583',
    });

    expect(descriptorOf(interp).molecularConsequences).toEqual([
      { id: 'SO:0001583', label: 'missense_variant' },
    ]);
  });

  it('omits molecularConsequences entirely when no consequence is known', () => {
    const wrapper = mountForm();
    const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B');

    expect(descriptorOf(interp)).not.toHaveProperty('molecularConsequences');
  });

  it('never writes a non-VRS variation object', () => {
    const wrapper = mountForm();
    const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B');

    expect(descriptorOf(interp)).not.toHaveProperty('variation');
  });

  it('records the notation as a VCF expression instead', () => {
    const wrapper = mountForm();
    const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B');

    expect(descriptorOf(interp).expressions).toEqual([
      { syntax: 'vcf', value: 'chr17-36459258-A-G' },
    ]);
  });

  it('never writes impact or caddScore onto VariantInterpretation', () => {
    const wrapper = mountForm();
    const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B', {
      impact: 'MODERATE',
      caddScore: 24.3,
    });
    const vi = interp.diagnosis.genomicInterpretations[0].variantInterpretation;

    expect(vi).not.toHaveProperty('impact');
    expect(vi).not.toHaveProperty('caddScore');
    expect(Object.keys(vi)).toEqual(['variationDescriptor']);
  });

  it('selects moleculeContext from the notation form', () => {
    const wrapper = mountForm();
    const t = (n) => descriptorOf(wrapper.vm.createInterpretation(n, 'HNF1B')).moleculeContext;

    expect(t('NM_000458.4:c.544+1G>A')).toBe('transcript');
    expect(t('NP_000449.1:p.Arg177Ter')).toBe('protein');
    expect(t('chr17-36459258-A-G')).toBe('genomic');
    expect(t('something-unrecognisable')).toBe('unspecified_molecule_context');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/components/VariantAnnotationForm.spec.js`
Expected: FAIL — `createInterpretation` is not exposed, and current output has `moleculeContext: 'missense_variant'`, a `variation` key, and `impact`/`caddScore`.

- [ ] **Step 3: Rewrite `createInterpretation` and expose it**

Replace `frontend/src/components/VariantAnnotationForm.vue` lines 242-286 with:

```javascript
/**
 * Pick the GA4GH MoleculeContext enum member implied by a notation.
 * GA4GH v2 admits exactly: unspecified_molecule_context | genomic | transcript | protein.
 */
const inferMoleculeContext = (notation) => {
  if (/:c\.|:n\./.test(notation)) return 'transcript';
  if (/:p\./.test(notation)) return 'protein';
  if (/^(chr)?[0-9XYMT]+[-:]/.test(notation) || /:g\./.test(notation)) return 'genomic';
  return 'unspecified_molecule_context';
};

/**
 * Create a GA4GH Phenopackets v2 interpretation.
 *
 * Deliberately does NOT write:
 *  - the VEP consequence into moleculeContext (it is an enum; the consequence
 *    goes to molecularConsequences as an SO term, matching the 424 corpus records)
 *  - a `variation` key (GA4GH requires a VRS Variation object; the notation is
 *    carried as a VCF expression instead)
 *  - impact / caddScore onto VariantInterpretation (it has exactly three fields:
 *    acmgPathogenicityClassification, therapeuticActionability, variationDescriptor).
 *    Both are derived annotation, re-fetchable from POST /api/v2/variants/annotate.
 */
const createInterpretation = (variantNotation, geneSymbol, annotationData = {}) => {
  const interpretationId = `interpretation-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

  const variationDescriptor = {
    id: `var:${variantNotation}`,
    label: variantNotation,
    geneContext: {
      valueId: geneSymbol === 'HNF1B' ? 'HGNC:5024' : '',
      symbol: geneSymbol,
    },
    moleculeContext: inferMoleculeContext(variantNotation),
    expressions: [{ syntax: 'vcf', value: variantNotation }],
  };

  if (annotationData.consequenceSoId && annotationData.consequence) {
    variationDescriptor.molecularConsequences = [
      { id: annotationData.consequenceSoId, label: annotationData.consequence },
    ];
  }

  return {
    id: interpretationId,
    progressStatus: 'IN_PROGRESS',
    diagnosis: {
      genomicInterpretations: [
        {
          subjectOrBiosampleId: props.subjectId,
          interpretationStatus: 'UNKNOWN',
          variantInterpretation: { variationDescriptor },
        },
      ],
    },
  };
};

defineExpose({ createInterpretation, inferMoleculeContext });
```

- [ ] **Step 3b: Supply the SO identifier the annotate endpoint does not return**

`POST /api/v2/variants/annotate` returns `most_severe_consequence` as a VEP term
string only — there is no SO ID in the response
(`backend/app/variant_validator_endpoint/annotate_route.py:138`). Without a mapping,
`molecularConsequences` would be silently omitted for every real annotation while the
unit test passes on a fabricated ID.

VEP consequence terms *are* SO terms, so the mapping is a lookup, not a judgement.
Add `frontend/src/utils/soTerms.js`:

```javascript
/**
 * VEP consequence term -> Sequence Ontology accession.
 *
 * VEP consequence names are SO term names, so this is a direct lookup rather
 * than an interpretation. POST /api/v2/variants/annotate returns only the term
 * name (annotate_route.py:138), and the corpus stores SO terms in
 * variationDescriptor.molecularConsequences, e.g. {id: "SO:0001483", label: "SNV"}.
 *
 * Covers the consequences HNF1B variants actually produce. An unmapped term
 * yields no molecularConsequences entry rather than a wrong one.
 * @see https://ensembl.org/info/genome/variation/prediction/predicted_data.html
 */
export const SO_TERMS = {
  transcript_ablation: 'SO:0001893',
  splice_acceptor_variant: 'SO:0001574',
  splice_donor_variant: 'SO:0001575',
  stop_gained: 'SO:0001587',
  frameshift_variant: 'SO:0001589',
  stop_lost: 'SO:0001578',
  start_lost: 'SO:0002012',
  transcript_amplification: 'SO:0001889',
  inframe_insertion: 'SO:0001821',
  inframe_deletion: 'SO:0001822',
  missense_variant: 'SO:0001583',
  protein_altering_variant: 'SO:0001818',
  splice_region_variant: 'SO:0001630',
  incomplete_terminal_codon_variant: 'SO:0001626',
  start_retained_variant: 'SO:0002019',
  stop_retained_variant: 'SO:0001567',
  synonymous_variant: 'SO:0001819',
  coding_sequence_variant: 'SO:0001580',
  mature_miRNA_variant: 'SO:0001620',
  '5_prime_UTR_variant': 'SO:0001623',
  '3_prime_UTR_variant': 'SO:0001624',
  non_coding_transcript_exon_variant: 'SO:0001792',
  intron_variant: 'SO:0001627',
  NMD_transcript_variant: 'SO:0001621',
  non_coding_transcript_variant: 'SO:0001619',
  upstream_gene_variant: 'SO:0001631',
  downstream_gene_variant: 'SO:0001632',
  intergenic_variant: 'SO:0001628',
  SNV: 'SO:0001483',
};

/** @returns {string|undefined} SO accession, or undefined if unmapped. */
export const soIdFor = (consequence) => SO_TERMS[consequence];
```

- [ ] **Step 3c: Update `addAnnotatedVariant`**

Replace lines 180-204's call so the SO ID is derived rather than expected from the
response, and impact/caddScore no longer reach the payload:

```javascript
import { soIdFor } from '@/utils/soTerms';

const interpretation = createInterpretation(
  variantInput.value,
  annotation.value.gene_symbol || 'HNF1B',
  {
    consequence: annotation.value.most_severe_consequence,
    consequenceSoId: soIdFor(annotation.value.most_severe_consequence),
  }
);
```

Add to the test file, so the real response shape is exercised rather than only the
helper:

```javascript
it('derives the SO id from the VEP term the annotate endpoint actually returns', () => {
  const wrapper = mountForm();
  // annotate_route.py:138 returns the term name only — no SO id.
  const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B', {
    consequence: 'missense_variant',
    consequenceSoId: soIdFor('missense_variant'),
  });

  expect(descriptorOf(interp).molecularConsequences).toEqual([
    { id: 'SO:0001583', label: 'missense_variant' },
  ]);
});

it('omits molecularConsequences for an unmapped consequence rather than guessing', () => {
  const wrapper = mountForm();
  const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B', {
    consequence: 'some_new_vep_term',
    consequenceSoId: soIdFor('some_new_vep_term'),
  });

  expect(descriptorOf(interp)).not.toHaveProperty('molecularConsequences');
});
```

with `import { soIdFor } from '@/utils/soTerms';` at the top of the spec.

- [ ] **Step 3d: Infer the expression syntax from the notation**

The form accepts HGVS, VCF and rsID (`VariantAnnotationForm.vue:49`), so labelling
every expression `syntax: 'vcf'` is wrong for two of the three. Replace the
`expressions` line in `createInterpretation`:

```javascript
    expressions: [{ syntax: inferExpressionSyntax(variantNotation), value: variantNotation }],
```

and add alongside `inferMoleculeContext`:

```javascript
/** Pick the VRSATILE expression syntax implied by a notation. */
const inferExpressionSyntax = (notation) => {
  if (/:c\./.test(notation)) return 'hgvs.c';
  if (/:p\./.test(notation)) return 'hgvs.p';
  if (/:g\./.test(notation)) return 'hgvs.g';
  if (/^rs\d+$/i.test(notation)) return 'dbsnp';
  return 'vcf';
};
```

All five syntaxes are already used by the corpus (`vcf` 864, `hgvs.g` 424,
`hgvs.c` 424, `hgvs.p` 363). Add a test asserting each mapping.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/components/VariantAnnotationForm.spec.js`
Expected: PASS, 7 tests.

- [ ] **Step 5: Verify the annotation display still works**

The `impact` and `caddScore` are still shown from `annotation.value` in the success alert (lines 72-93) — that markup is unchanged and reads the composable's response, not the payload. Confirm the variant list subtitle no longer references removed payload fields by checking `variants` computed (lines 136-156): `variant.impact` and `variant.caddScore` now resolve to `undefined` and the `v-if`/`v-show` guards hide them.

Update the `variants` computed to read from the new location:

```javascript
return {
  label: descriptor.label || descriptor.id || 'Unknown variant',
  geneSymbol: descriptor.geneContext?.symbol,
  consequence: descriptor.molecularConsequences?.[0]?.label,
  moleculeContext: descriptor.moleculeContext,
};
```

and in the template (lines 21-28) replace the `impact`/`caddScore` spans with:

```html
<v-list-item-subtitle v-if="variant.geneSymbol">
  Gene: {{ variant.geneSymbol }}
  <span v-if="variant.consequence"> | {{ variant.consequence }}</span>
</v-list-item-subtitle>
```

- [ ] **Step 6: Run the full frontend gate**

Run: `cd frontend && npx vitest run && npm run lint:check && npx prettier --check src tests`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/VariantAnnotationForm.vue frontend/tests/unit/components/VariantAnnotationForm.spec.js
git commit -m "fix(curation): stop writing malformed variant payloads (B1, B2, B7)

moleculeContext received the VEP consequence string where GA4GH admits only
unspecified_molecule_context|genomic|transcript|protein. variation received
{notation} where a VRS Variation object belongs. impact and caddScore were
written onto VariantInterpretation, which has exactly three fields.

Consequence now goes to variationDescriptor.molecularConsequences as an SO
term, matching the 424 corpus records that already use it. Notation is carried
as a vcf expression. impact/caddScore are display-only, re-fetchable from
POST /api/v2/variants/annotate.

Refs: docs/superpowers/specs/2026-07-30-curation-data-model-design.md"
```

---

## Task 2: Stop persisting the undocumented `publications` key (B3)

`PhenopacketCreateEdit.vue` keeps a `publications` array **on the phenopacket object itself** (`:209`), and `buildSubmissionPhenopacket` spreads the whole object into the payload (`:326`). `publications` is not a Phenopackets v2 field, the schema has no `additionalProperties: false`, and the sanitizer only strips nulls and empties (`sanitizer.py:22-38`) — so it is persisted verbatim.

It happens to be invisible today only because an *empty* array is dropped by `remove_empty`. The moment a curator adds one PMID, the key lands in the JSONB. All 923 existing records have exactly six top-level keys.

**Files:**
- Modify: `frontend/src/views/PhenopacketCreateEdit.vue:199-232, 282-287, 303-332`
- Modify: `frontend/tests/unit/views/PhenopacketCreateEdit.spec.js` — **this file already exists** (180 lines, three tests) and currently asserts the *opposite* of the desired behaviour: `:131` and `:171` both assert `publications` IS present in the submitted payload. Those assertions encode the bug and must be inverted, not appended to.

**Interfaces:**
- Consumes: nothing.
- Produces: `buildSubmissionPhenopacket() → Phenopacket` with no `publications` key, reading PMIDs from `this.publications`. Task 10's export test asserts the same invariant server-side.

- [ ] **Step 1: Read the existing test file**

Run: `cat frontend/tests/unit/views/PhenopacketCreateEdit.spec.js`

Note that `createContext()` (`:43-78`) puts `publications: []` **inside** `phenopacket`, and that all three tests drive `loadPhenopacket` / `handleSubmit` rather than `buildSubmissionPhenopacket` directly. The rewrite keeps that structure — only the location of `publications` changes.

- [ ] **Step 2: Rewrite the existing tests against the new location**

In `createContext` (`:63-75`), move `publications` out of `phenopacket` to a sibling, and add the builder helper reference already present at `:62`:

```javascript
    publications: [],
    phenopacket: {
      id: 'PP-001',
      subject: { id: 'SUB-001', sex: 'UNKNOWN_SEX' },
      phenotypicFeatures: [],
      interpretations: [],
      metaData: { externalReferences: [] },
    },
    ...overrides,
```

Update the three existing tests:

- `:91` "loads PMID publications into phenopacket.publications" → rename to "loads PMID publications into component state" and assert `ctx.publications` instead of `ctx.phenopacket.publications`.
- `:103` and `:141` → move `publications: [{ pmid: '12345678' }]` from the nested `phenopacket` object into the top-level override, and change each `expect.objectContaining({ publications: ... })` to assert its **absence**:

```javascript
    expect(updatePhenopacket).toHaveBeenCalledWith('PP-001', {
      phenopacket: expect.not.objectContaining({ publications: expect.anything() }),
      revision: 7,
      change_reason: 'Updated publication list',
    });

    const submitted = updatePhenopacket.mock.calls[0][1].phenopacket;
    expect(submitted.metaData.externalReferences).toEqual([{ id: 'PMID:12345678' }]);
```

Then append the new direct-builder tests:

```javascript
describe('buildSubmissionPhenopacket', () => {
  const build = PhenopacketCreateEdit.methods.buildSubmissionPhenopacket;

  it('never emits a top-level publications key', () => {
    const out = build.call(createContext({ publications: [{ pmid: '25324567' }] }));
    expect(out).not.toHaveProperty('publications');
  });

  it('strips a legacy publications key that arrives on a loaded record', () => {
    // Records saved before this fix carry the key inside the stored document.
    // Loading and re-saving one must not perpetuate it.
    const ctx = createContext({ publications: [{ pmid: '25324567' }] });
    ctx.phenopacket.publications = [{ pmid: 'stale' }];

    expect(build.call(ctx)).not.toHaveProperty('publications');
  });

  it('promotes PMIDs to metaData.externalReferences in order', () => {
    const out = build.call(
      createContext({ publications: [{ pmid: '25324567' }, { pmid: '20378641' }] })
    );
    expect(out.metaData.externalReferences).toEqual([
      { id: 'PMID:25324567' },
      { id: 'PMID:20378641' },
    ]);
  });

  it('drops blank PMID rows', () => {
    const out = build.call(
      createContext({ publications: [{ pmid: '  ' }, { pmid: '25324567' }] })
    );
    expect(out.metaData.externalReferences).toEqual([{ id: 'PMID:25324567' }]);
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd frontend && npx vitest run tests/unit/views/PhenopacketCreateEdit.spec.js`
Expected: FAIL — `publications` is still emitted, because it lives on `this.phenopacket` and is spread through.

- [ ] **Step 4: Move `publications` off the phenopacket into component state**

In `data()` (line 199), remove `publications: []` from the `phenopacket` object and add a sibling:

```javascript
data() {
  return {
    phenopacket: {
      id: '',
      subject: { id: '', sex: 'UNKNOWN_SEX' },
      phenotypicFeatures: [],
      interpretations: [],
      metaData: { /* unchanged */ },
    },
    // Editor-only state. Deliberately NOT on `phenopacket`: `publications` is
    // not a Phenopackets v2 field, and buildSubmissionPhenopacket spreads that
    // object wholesale. PMIDs are promoted to metaData.externalReferences on save.
    publications: [],
    // ... rest unchanged
  };
}
```

- [ ] **Step 5: Update every reference from `phenopacket.publications` to `publications`**

Template (line 86): `v-for="(pub, index) in publications"`.

`loadPhenopacket` (lines 282-287):

```javascript
this.publications = (this.phenopacket.metaData?.externalReferences || [])
  .filter((ref) => ref.id?.startsWith('PMID:'))
  .map((ref) => ({ pmid: ref.id.replace('PMID:', '') }));
```

and its log field (line 291): `publicationsLoaded: this.publications.length`.

`addPublication` / `removePublication` (lines 303-311):

```javascript
addPublication() {
  this.publications.push({ pmid: '' });
},

removePublication(index) {
  this.publications.splice(index, 1);
},
```

`buildSubmissionPhenopacket` (lines 313-332). Note the destructure: records saved
before this fix carry `publications` inside the stored document, so loading and
re-saving one would otherwise perpetuate the key.

```javascript
buildSubmissionPhenopacket() {
  // `publications` is destructured out and discarded: it is not a Phenopackets
  // v2 field, and records saved before this fix may carry it in the loaded
  // document. `this.publications` (component state) is the source of truth.
  // eslint-disable-next-line no-unused-vars
  const { publications: _legacyPublications, ...phenopacket } = this.phenopacket;

  const existingReferences = phenopacket.metaData?.externalReferences || [];
  const nonPmidExternalReferences = existingReferences.filter(
    (ref) => !ref.id?.startsWith('PMID:')
  );
  const pmidExternalReferences = this.publications
    .map((pub) => `${pub.pmid || ''}`.trim())
    .filter(Boolean)
    .map((pmid) => ({ id: `PMID:${pmid}` }));

  return {
    ...phenopacket,
    metaData: {
      ...(phenopacket.metaData || {}),
      externalReferences: [...nonPmidExternalReferences, ...pmidExternalReferences],
    },
  };
},
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run tests/unit/views/PhenopacketCreateEdit.spec.js`
Expected: PASS — the three rewritten tests plus four new ones.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/PhenopacketCreateEdit.vue frontend/tests/unit/views/PhenopacketCreateEdit.spec.js
git commit -m "fix(curation): keep the publications editor off the phenopacket payload (B3)

publications lived on this.phenopacket and buildSubmissionPhenopacket spreads
that object wholesale, so the key was persisted into the JSONB. It is not a
Phenopackets v2 field; the schema has no additionalProperties:false and the
sanitizer only strips nulls/empties. It was latent only because an empty array
is dropped by remove_empty — adding one PMID would have persisted it.

All 923 existing records have exactly six top-level keys.

Refs: docs/superpowers/specs/2026-07-30-curation-data-model-design.md"
```

---

## Task 3: Fix the prop mutation in the phenotype tri-state (B6)

`cycleState` shallow-copies the array with `[...props.modelValue]`, then writes `updated[index].excluded = true`. The element is the *same object* the parent owns, so present→excluded mutates the prop directly. It works only because the parent happens to re-render.

**Files:**
- Modify: `frontend/src/components/PhenotypicFeaturesSection.vue:223-268`
- Test: `frontend/tests/unit/components/PhenotypicFeaturesSection.spec.js` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `cycleState(term)` and `selectCKDStage(stages, id)` emit new arrays whose elements are new objects. The Phase 3 grid replaces this component but preserves the emitted value shape `{type: {id, label}, excluded: boolean}`.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/unit/components/PhenotypicFeaturesSection.spec.js`:

```javascript
import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import PhenotypicFeaturesSection from '@/components/PhenotypicFeaturesSection.vue';

vi.mock('@/composables/useGroupedHPO', () => ({
  useGroupedHPO: () => ({
    groups: { value: { Kidney: [{ hpo_id: 'HP:0000107', label: 'Renal cyst' }] } },
    loading: { value: false },
    fetchGrouped: vi.fn(),
  }),
}));

const vuetify = createVuetify();
const TERM = { hpo_id: 'HP:0000107', label: 'Renal cyst' };

function mountSection(modelValue) {
  return mount(PhenotypicFeaturesSection, {
    props: { modelValue },
    global: { plugins: [vuetify] },
  });
}

describe('PhenotypicFeaturesSection state transitions', () => {
  it('does not mutate the prop array when cycling present -> excluded', () => {
    const original = [{ type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: false }];
    const snapshot = structuredClone(original);
    const wrapper = mountSection(original);

    wrapper.vm.cycleState(TERM);

    expect(original).toEqual(snapshot);
  });

  it('emits a new element object rather than the prop element', () => {
    const original = [{ type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: false }];
    const wrapper = mountSection(original);

    wrapper.vm.cycleState(TERM);
    const emitted = wrapper.emitted('update:modelValue')[0][0];

    expect(emitted[0]).not.toBe(original[0]);
    expect(emitted[0].excluded).toBe(true);
  });

  it('cycles unknown -> present -> excluded -> unknown', () => {
    let model = [];
    const step = () => {
      const wrapper = mountSection(model);
      wrapper.vm.cycleState(TERM);
      model = wrapper.emitted('update:modelValue')[0][0];
      return model;
    };

    expect(step()).toEqual([{ type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: false }]);
    expect(step()).toEqual([{ type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: true }]);
    expect(step()).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/components/PhenotypicFeaturesSection.spec.js`
Expected: FAIL on the first two tests — `original[0].excluded` becomes `true`, and the emitted element is the same object reference.

- [ ] **Step 3: Replace the element instead of mutating it**

Replace `cycleState` (lines 223-243):

```javascript
// Cycle through states: unknown -> present -> excluded -> unknown.
// Never mutates props.modelValue: `[...arr]` is a shallow copy, so writing
// `copy[i].excluded` would write through to the parent's own object.
const cycleState = (term) => {
  const index = props.modelValue.findIndex((f) => f.type?.id === term.hpo_id);
  const currentState = getState(term.hpo_id);
  const updated = [...props.modelValue];

  if (currentState === 0) {
    updated.push({ type: { id: term.hpo_id, label: term.label }, excluded: false });
  } else if (currentState === 1) {
    updated[index] = { ...updated[index], excluded: true };
  } else {
    updated.splice(index, 1);
  }

  emit('update:modelValue', updated);
};
```

`selectCKDStage` (lines 253-268) already builds a fresh object and filters rather than mutating, so it needs no change. Add a clarifying comment above it:

```javascript
// Builds a fresh array and a fresh element; safe as written.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/components/PhenotypicFeaturesSection.spec.js`
Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PhenotypicFeaturesSection.vue frontend/tests/unit/components/PhenotypicFeaturesSection.spec.js
git commit -m "fix(curation): stop mutating the modelValue prop in cycleState (B6)

[...arr] is a shallow copy, so updated[index].excluded = true wrote through to
the parent's own element. Replace the element instead.

Refs: docs/superpowers/specs/2026-07-30-curation-data-model-design.md"
```

---

## Task 4: Make age render, and delete the dead `age_utils` module

Two frontend readers query `subject.timeAtLastEncounter.age.iso8601duration`. **Zero of 923 records use that path** — the corpus stores `{"iso8601duration": …}` flat, in 664 records. So last-encounter age never displays.

Per ADR 0003 the data is not migrated; the readers are corrected. Both shapes are accepted so the eventual conformance migration needs no second frontend change.

`backend/app/phenopackets/age_utils.py` is separately dead — nothing in the repository imports it — and its SQL is invalid regardless: `phenopacket->>'subject'->>'timeAtLastEncounter'` raises `operator does not exist: text ->> unknown`, because the first `->>` returns text. Delete it rather than repair it.

**Files:**
- Modify: `frontend/src/components/phenopacket/SubjectCard.vue:117-123`
- Modify: `frontend/src/views/PagePhenopacket.vue:445-460`
- Modify: `frontend/src/schemas/phenopacketSchema.js:20-24`
- Delete: `backend/app/phenopackets/age_utils.py`
- Test: `frontend/tests/unit/components/SubjectCard.spec.js` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `readEncounterAge(subject) → string | null`, a shared helper. The Phase 3 console's age control reads and writes through the same helper.

- [ ] **Step 1: Confirm `age_utils` really is unreferenced**

Run:

```bash
grep -rn "age_utils" --include=*.py . | grep -v '\.venv' | grep -v __pycache__ | grep -v 'app/phenopackets/age_utils.py'
```

Expected: no output. If anything is printed, stop — the deletion in Step 7 is unsafe and the module must be repaired instead.

- [ ] **Step 2: Write the failing test**

Create `frontend/tests/unit/components/SubjectCard.spec.js`:

```javascript
import { describe, it, expect } from 'vitest';
import { readEncounterAge } from '@/utils/age';

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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/components/SubjectCard.spec.js`
Expected: FAIL — `@/utils/age` does not exist.

- [ ] **Step 4: Create the shared helper**

Create `frontend/src/utils/age.js`:

```javascript
/**
 * Read the age at last encounter from a GA4GH subject.
 *
 * Accepts both shapes on purpose:
 *  - `{age: {iso8601duration}}`  GA4GH-conformant; 0 records use it today
 *  - `{iso8601duration}`         the corpus convention; 664 records
 *
 * The corpus is not migrated (see docs/adr/0003-ga4gh-conformance-debt.md),
 * so both must be read until that debt is paid. Accepting both now means the
 * migration needs no second frontend change.
 *
 * @param {object|null|undefined} subject GA4GH Individual
 * @returns {string|null} ISO-8601 duration, or null when no age is recorded
 */
export function readEncounterAge(subject) {
  const t = subject?.timeAtLastEncounter;
  if (!t) return null;
  return t.age?.iso8601duration ?? t.iso8601duration ?? null;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/components/SubjectCard.spec.js`
Expected: PASS, 5 tests.

- [ ] **Step 6: Wire the helper into both readers**

`frontend/src/components/phenopacket/SubjectCard.vue` — add the import alongside the existing imports, then replace the `age()` computed (lines 117-123):

```javascript
age() {
  const duration = readEncounterAge(this.subject);
  return duration ? this.formatISO8601Duration(duration) : null;
},
```

`frontend/src/views/PagePhenopacket.vue` — add the import, then replace `ageDisplay()` (lines 445-460):

```javascript
ageDisplay() {
  const subject = this.phenopacket?.subject;
  if (!subject) return 'N/A';

  const encounterAge = readEncounterAge(subject);
  if (encounterAge) return this.formatISO8601Duration(encounterAge);

  // Deceased individuals may record only an age at death.
  if (subject.vitalStatus?.timeOfDeath?.age?.iso8601duration) {
    return this.formatISO8601Duration(subject.vitalStatus.timeOfDeath.age.iso8601duration);
  }

  return 'N/A';
},
```

`frontend/src/schemas/phenopacketSchema.js` — widen the shape (lines 20-24):

```javascript
  // Both shapes are valid input: the GA4GH-conformant `age` wrapper and the
  // flat corpus convention. See docs/adr/0003-ga4gh-conformance-debt.md.
  timeAtLastEncounter: yup.object({
    iso8601duration: yup.string().matches(/^P/, 'Invalid ISO8601 duration format'),
    age: yup.object({
      iso8601duration: yup.string().matches(/^P/, 'Invalid ISO8601 duration format'),
    }),
    gestationalAge: yup.object({
      weeks: yup.number().integer().min(0).max(45),
      days: yup.number().integer().min(0).max(6),
    }),
  }),
```

- [ ] **Step 7: Delete the dead backend module**

```bash
git rm backend/app/phenopackets/age_utils.py
```

- [ ] **Step 8: Run both gates**

Run: `cd frontend && npx vitest run && npm run lint:check && npx prettier --check src tests`
Run: `cd backend && uv run ruff format && uv run ruff check . && uv run pytest -q`
Expected: all pass. The backend suite needs the docker pgvector/pg15 + redis services up; `conftest` self-migrates.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/utils/age.js frontend/src/components/phenopacket/SubjectCard.vue \
        frontend/src/views/PagePhenopacket.vue frontend/src/schemas/phenopacketSchema.js \
        frontend/tests/unit/components/SubjectCard.spec.js
git commit -m "fix(curation): make age at last encounter render; drop dead age_utils

Both frontend readers queried timeAtLastEncounter.age.iso8601duration, which
0 of 923 records use — the corpus stores it flat, in 664 records. A shared
readEncounterAge() helper accepts both shapes so the eventual conformance
migration needs no second frontend change.

backend/app/phenopackets/age_utils.py had no importers anywhere in the repo and
its SQL was invalid regardless: phenopacket->>'subject'->>'timeAtLastEncounter'
raises 'operator does not exist: text ->> unknown'.

Refs: docs/adr/0003-ga4gh-conformance-debt.md"
```

---

# Phase 2 — Storage contract

## Task 5: Add the four controlled-vocabulary tables

Four reference tables following the `sex_values` pattern from
`88b3a0c19a89_add_phenopacket_controlled_vocabularies`. Raw-SQL managed, no ORM model, so each must be registered in `include_object` or `test_alembic_env_autogenerate.py` emits `op.drop_table` for it.

Values and counts come from the spreadsheet (939 rows).

**Files:**
- Create: `backend/alembic/versions/a1c4e7f20b93_add_curation_vocabularies.py`
- Modify: `backend/alembic/env.py:141-152`
- Modify: `backend/tests/test_alembic_env_autogenerate.py:48` — a **second, independent** registry that also needs the four names
- Test: `backend/tests/test_curation_vocabularies.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: tables `cohort_values`, `detection_method_values`, `segregation_values`, `family_history_values`, each `(value text PK, label text, description text, sort_order int)`. Task 6 selects from them; Task 9 validates against them.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_curation_vocabularies.py`:

```python
"""Reference tables backing the curation vocabularies (spec §4.6)."""

import pytest
from sqlalchemy import text

VOCAB_TABLES = [
    "cohort_values",
    "detection_method_values",
    "segregation_values",
    "family_history_values",
]

EXPECTED_VALUES = {
    "cohort_values": {"born", "fetus"},
    "detection_method_values": {
        "sanger", "ngs", "cma", "mlpa", "qpcr", "fish", "other", "not_reported",
    },
    "segregation_values": {
        "de_novo", "inherited_maternal", "inherited_paternal",
        "inherited_unspecified", "not_reported",
    },
    "family_history_values": {"positive", "negative", "not_reported"},
}


@pytest.mark.parametrize("table", VOCAB_TABLES)
@pytest.mark.asyncio
async def test_table_exists_with_expected_columns(db_session, table):
    result = await db_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t ORDER BY column_name"
        ),
        {"t": table},
    )
    columns = {row[0] for row in result.fetchall()}
    assert {"value", "label", "description", "sort_order"} <= columns


@pytest.mark.parametrize("table", VOCAB_TABLES)
@pytest.mark.asyncio
async def test_seeded_with_expected_values(db_session, table):
    result = await db_session.execute(text(f"SELECT value FROM {table}"))  # noqa: S608
    assert {row[0] for row in result.fetchall()} == EXPECTED_VALUES[table]


@pytest.mark.parametrize("table", VOCAB_TABLES)
@pytest.mark.asyncio
async def test_sort_order_is_dense_and_unique(db_session, table):
    result = await db_session.execute(
        text(f"SELECT sort_order FROM {table} ORDER BY sort_order")  # noqa: S608
    )
    orders = [row[0] for row in result.fetchall()]
    assert orders == list(range(1, len(orders) + 1))


@pytest.mark.asyncio
async def test_not_reported_present_where_the_source_records_silence(db_session):
    """`not_reported` means the curator read the source and it was silent.

    Cohort is excluded on purpose: the spreadsheet states it for all 939 rows,
    so absence of the key means 'not yet curated' instead.
    """
    for table in ("detection_method_values", "segregation_values", "family_history_values"):
        result = await db_session.execute(
            text(f"SELECT 1 FROM {table} WHERE value = 'not_reported'")  # noqa: S608
        )
        assert result.first() is not None, table

    result = await db_session.execute(
        text("SELECT 1 FROM cohort_values WHERE value = 'not_reported'")
    )
    assert result.first() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_curation_vocabularies.py -q`
Expected: FAIL — relations do not exist.

- [ ] **Step 3: Write the migration**

Create `backend/alembic/versions/a1c4e7f20b93_add_curation_vocabularies.py`:

```python
"""Add curation controlled vocabularies.

Reference tables for the curation storage contract: cohort, detection method,
segregation and family history. Follows the sex_values pattern from
88b3a0c19a89_add_phenopacket_controlled_vocabularies — raw SQL, no ORM model,
registered in alembic/env.py::include_object.

Values and counts are taken from HNF1B_DataCuration.xlsx (939 rows). Counts are
recorded in the description column for curator context, not enforced.

Revision ID: a1c4e7f20b93
Revises: <set to current head>
"""

from alembic import op

revision = "a1c4e7f20b93"
down_revision = None  # set to the current head before running
branch_labels = None
depends_on = None

_TABLES = {
    "cohort_values": [
        ("born", "Born", "Live-born individual", 1),
        ("fetus", "Fetus", "Prenatal case; pregnancy termination or fetal assessment", 2),
    ],
    "detection_method_values": [
        ("sanger", "Sanger sequencing", None, 1),
        ("ngs", "Next-generation sequencing", None, 2),
        ("cma", "Chromosomal microarray", None, 3),
        ("mlpa", "MLPA", "Multiplex ligation-dependent probe amplification", 4),
        ("qpcr", "qPCR", "Quantitative PCR", 5),
        ("fish", "FISH", "Fluorescence in situ hybridisation", 6),
        ("other", "Other", "Method stated but not one of the above", 7),
        ("not_reported", "Not reported", "Source is silent on detection method", 8),
    ],
    "segregation_values": [
        ("de_novo", "De novo", "Not present in either parent", 1),
        ("inherited_maternal", "Inherited, maternal", None, 2),
        ("inherited_paternal", "Inherited, paternal", None, 3),
        ("inherited_unspecified", "Inherited, parent unspecified", None, 4),
        ("not_reported", "Not reported", "Source is silent on segregation", 5),
    ],
    "family_history_values": [
        ("positive", "Positive", "Relatives reported with a related phenotype", 1),
        ("negative", "Negative", "Family history explicitly reported as negative", 2),
        ("not_reported", "Not reported", "Source is silent on family history", 3),
    ],
}


def _lit(value: str | None) -> str:
    """Render a SQL string literal, or NULL."""
    if value is None:
        return "NULL"
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def upgrade() -> None:
    for table, rows in _TABLES.items():
        op.execute(
            f"""
            CREATE TABLE {table} (
                value       text PRIMARY KEY,
                label       text NOT NULL,
                description text,
                sort_order  integer NOT NULL
            )
            """  # noqa: S608
        )
        for value, label, description, sort_order in rows:
            op.execute(
                f"""
                INSERT INTO {table} (value, label, description, sort_order)
                VALUES ({_lit(value)}, {_lit(label)}, {_lit(description)}, {sort_order})
                """  # noqa: S608
            )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")  # noqa: S608
```

- [ ] **Step 4: Set the revision parent**

Run: `cd backend && uv run alembic heads`

Set `down_revision` in the new file to the printed head. If more than one head is printed, stop and resolve the branch first.

- [ ] **Step 5: Register the tables in BOTH registries**

There are two independent lists, and missing either fails the drift test:

1. `backend/alembic/env.py::include_object` — what autogenerate actually filters.
2. `backend/tests/test_alembic_env_autogenerate.py:48` `_RAW_SQL_TABLES` — the test
   maintains its **own copy** and re-implements the filter at `:77`. Updating only
   `env.py` leaves the test reporting all four tables as removal candidates.

Add all four names to `_RAW_SQL_TABLES` as well, alphabetically:

```python
_RAW_SQL_TABLES = {
    "alembic_version",
    "allelic_state_values",
    "cohort_values",
    "detection_method_values",
    "evidence_code_values",
    "family_history_values",
    "hpo_terms_lookup",
    "interpretation_status_values",
    "progress_status_values",
    "publication_metadata",
    "publication_fulltext",
    "publication_fulltext_embeddings",
    "segregation_values",
    "sex_values",
    "variant_annotations",
}
```

Then in `backend/alembic/env.py`, add to the docstring's bullet list:

```
    * ``cohort_values``, ``detection_method_values``, ``segregation_values``,
      ``family_history_values`` — curation controlled-vocabulary tables from
      ``a1c4e7f20b93_add_curation_vocabularies``.
```

and add the four names to the set at lines 141-152, keeping alphabetical order:

```python
    if type_ == "table" and name in {
        "alembic_version",
        "allelic_state_values",
        "cohort_values",
        "detection_method_values",
        "evidence_code_values",
        "family_history_values",
        "hpo_terms_lookup",
        "interpretation_status_values",
        "progress_status_values",
        "publication_metadata",
        "publication_fulltext",
        "publication_fulltext_embeddings",
        "segregation_values",
        "sex_values",
        "variant_annotations",
    }:
        return False
    return True
```

- [ ] **Step 6: Run the migration and the tests**

Run: `cd backend && uv run alembic upgrade head && uv run pytest tests/test_curation_vocabularies.py tests/test_alembic_env_autogenerate.py -q`
Expected: PASS. The autogenerate-drift test must stay green — if it now proposes dropping the new tables, Step 5 was missed.

- [ ] **Step 7: Verify downgrade**

Run: `cd backend && uv run alembic downgrade -1 && uv run alembic upgrade head`
Expected: both succeed; re-running the vocabulary tests still passes.

- [ ] **Step 8: Commit**

```bash
cd backend && uv run ruff format && cd ..
git add backend/alembic/versions/a1c4e7f20b93_add_curation_vocabularies.py backend/alembic/env.py backend/tests/test_curation_vocabularies.py
git commit -m "feat(curation): add cohort/detection-method/segregation/family-history vocabularies

Four raw-SQL reference tables following the sex_values pattern, registered in
alembic/env.py::include_object so the autogenerate-drift test does not propose
dropping them.

cohort_values deliberately has no not_reported member: the source states cohort
for all 939 rows, so absence means 'not yet curated' rather than 'source silent'.

Refs: docs/superpowers/specs/2026-07-30-curation-data-model-design.md §4.6"
```

---

## Task 6: Expose the four vocabularies over the API

Existing vocabulary endpoints are **not** uniform: `sex` returns `{value,label,description}`, `interpretation-status` adds `category`, `allelic-state` and `evidence-code` key on `id` rather than `value`. All wrap in `{"data": [...]}`.

New endpoints declare an explicit response model with one canonical item shape rather than inheriting that inconsistency.

**Files:**
- Modify: `backend/app/ontology/routers.py` (append after `get_evidence_code_values`)
- Create: `backend/app/ontology/schemas.py` if absent, else modify
- Test: `backend/tests/test_curation_vocabulary_endpoints.py` (create)

**Interfaces:**
- Consumes: Task 5's four tables.
- Produces: `GET /api/v2/ontology/vocabularies/{cohort,detection-method,segregation,family-history}` → `{"data": [{"value": str, "label": str, "description": str | None}]}`. Task 11's composable and Task 12's MCP `Literal` consume these paths.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_curation_vocabulary_endpoints.py`:

```python
"""Curation vocabulary endpoints (spec §4.6)."""

import pytest

ENDPOINTS = {
    "cohort": {"born", "fetus"},
    "detection-method": {
        "sanger", "ngs", "cma", "mlpa", "qpcr", "fish", "other", "not_reported",
    },
    "segregation": {
        "de_novo", "inherited_maternal", "inherited_paternal",
        "inherited_unspecified", "not_reported",
    },
    "family-history": {"positive", "negative", "not_reported"},
}


@pytest.mark.parametrize("name,expected", ENDPOINTS.items())
@pytest.mark.asyncio
async def test_returns_expected_values(async_client, name, expected):
    response = await async_client.get(f"/api/v2/ontology/vocabularies/{name}")
    assert response.status_code == 200
    assert {item["value"] for item in response.json()["data"]} == expected


@pytest.mark.parametrize("name", ENDPOINTS)
@pytest.mark.asyncio
async def test_item_shape_is_canonical(async_client, name):
    """One shape across all four, unlike the pre-existing vocabulary endpoints."""
    response = await async_client.get(f"/api/v2/ontology/vocabularies/{name}")
    for item in response.json()["data"]:
        assert set(item) == {"value", "label", "description"}
        assert isinstance(item["value"], str)
        assert isinstance(item["label"], str)


@pytest.mark.asyncio
async def test_detection_method_is_ordered_by_sort_order(async_client):
    response = await async_client.get("/api/v2/ontology/vocabularies/detection-method")
    values = [item["value"] for item in response.json()["data"]]
    assert values == [
        "sanger", "ngs", "cma", "mlpa", "qpcr", "fish", "other", "not_reported",
    ]


@pytest.mark.asyncio
async def test_cohort_has_no_not_reported(async_client):
    """Absence of the key means 'not yet curated'; the source always states cohort."""
    response = await async_client.get("/api/v2/ontology/vocabularies/cohort")
    assert "not_reported" not in {item["value"] for item in response.json()["data"]}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_curation_vocabulary_endpoints.py -q`
Expected: FAIL with 404 — routes do not exist.

- [ ] **Step 3: Add the response model**

In `backend/app/ontology/schemas.py` (create if absent, with a module docstring):

```python
"""Response models for ontology and controlled-vocabulary endpoints."""

from typing import List, Optional

from pydantic import BaseModel, Field


class VocabularyItem(BaseModel):
    """One controlled-vocabulary member.

    The canonical shape for vocabularies added by the curation storage contract.
    Pre-existing endpoints (sex, interpretation-status, allelic-state,
    evidence-code) have divergent shapes and are deliberately left alone.
    """

    value: str = Field(..., description="Stored token, e.g. 'mlpa'")
    label: str = Field(..., description="Curator-facing label, e.g. 'MLPA'")
    description: Optional[str] = Field(None, description="Optional clarifying text")


class VocabularyResponse(BaseModel):
    """Envelope matching every other vocabulary endpoint in this API."""

    data: List[VocabularyItem]
```

- [ ] **Step 4: Add the routes**

Append to `backend/app/ontology/routers.py`, after `get_evidence_code_values`:

```python
_CURATION_VOCABULARIES = {
    "cohort": "cohort_values",
    "detection-method": "detection_method_values",
    "segregation": "segregation_values",
    "family-history": "family_history_values",
}


async def _fetch_curation_vocabulary(db: AsyncSession, table: str) -> VocabularyResponse:
    """Read one curation reference table in sort_order.

    The table name comes from the module-level mapping, never from user input.
    """
    query = text(
        f"SELECT value, label, description FROM {table} ORDER BY sort_order"  # noqa: S608
    )
    result = await db.execute(query)
    return VocabularyResponse(data=[dict(row._mapping) for row in result.fetchall()])


@router.get("/vocabularies/cohort", response_model=VocabularyResponse)
async def get_cohort_values(db: AsyncSession = Depends(get_db)):
    """Get valid cohort values (born / fetus) for hnf1bCuration.cohort."""
    return await _fetch_curation_vocabulary(db, _CURATION_VOCABULARIES["cohort"])


@router.get("/vocabularies/detection-method", response_model=VocabularyResponse)
async def get_detection_method_values(db: AsyncSession = Depends(get_db)):
    """Get valid variant detection methods for hnf1bCuration.detectionMethod."""
    return await _fetch_curation_vocabulary(db, _CURATION_VOCABULARIES["detection-method"])


@router.get("/vocabularies/segregation", response_model=VocabularyResponse)
async def get_segregation_values(db: AsyncSession = Depends(get_db)):
    """Get valid segregation origins for the variationDescriptor segregation extension."""
    return await _fetch_curation_vocabulary(db, _CURATION_VOCABULARIES["segregation"])


@router.get("/vocabularies/family-history", response_model=VocabularyResponse)
async def get_family_history_values(db: AsyncSession = Depends(get_db)):
    """Get valid family history statuses for hnf1bCuration.familyHistory."""
    return await _fetch_curation_vocabulary(db, _CURATION_VOCABULARIES["family-history"])
```

Add the import at the top of the module:

```python
from app.ontology.schemas import VocabularyResponse
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_curation_vocabulary_endpoints.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd backend && uv run ruff format && cd ..
git add backend/app/ontology/routers.py backend/app/ontology/schemas.py backend/tests/test_curation_vocabulary_endpoints.py
git commit -m "feat(curation): expose the four curation vocabularies over the API

Explicit VocabularyResponse model with one canonical {value,label,description}
item shape. The pre-existing vocabulary endpoints are inconsistent — sex adds
description, interpretation-status adds category, allelic-state and
evidence-code key on id — and are deliberately left as they are.

Refs: docs/superpowers/specs/2026-07-30-curation-data-model-design.md §4.6"
```

---

## Task 7: Add per-term laterality policy and its endpoint

Laterality is restored as HPO modifiers. Which modifiers a term admits is **reference data**, not a constant, because of one asymmetry: HP:0000122 *Unilateral renal agenesis* already asserts unilaterality, so it must reject Bilateral as contradictory.

> **AMENDED 2026-07-30 (adversarial review, user-confirmed).** This task originally gave
> HP:0000122 `{Left, Right}` only, rejecting `Unilateral` as redundant. That is wrong. The
> source carries 48 laterality values on `SolitaryKidney` (which the sheet maps to HP:0000122),
> of which **20 are `unilateral unspecified`**. Rejecting `Unilateral` would force the ontology
> plan's Task 4 backfill to drop those 20, leaving the features with no modifier at all —
> indistinguishable from "laterality never stated", which is precisely the defect
> `docs/ontology-defect-report-2026-07-30.md` §3 exists to condemn. Clinical redundancy is not
> the same as provenance-losslessness.
>
> HP:0000122 therefore admits `{Unilateral, Left, Right}` and rejects only `Bilateral`.
> `parse_laterality()` needs no term-awareness, the ontology plan's Task 4 invariant
> "`Left`/`Right` never appear without `Unilateral`" remains globally true, and no second
> encoding of the policy is created.
>
> Verified no consumer breaks on a side-only or bare-`Unilateral` modifier list:
> `schema_validator.py:108-111` types `modifiers` as an unordered array of `ontologyClass`, and
> `PhenotypicFeaturesCard.vue:218` renders `modifiers.map((m) => m.label || m.id).join(', ')`
> with no positional interpretation.

**Files:**
- Create: `backend/alembic/versions/c8f1a3d5e207_add_hpo_allowed_modifiers.py`
- Modify: `backend/app/ontology/routers.py`
- Test: `backend/tests/test_laterality_policy.py` (create)

**Interfaces:**
- Consumes: `hpo_terms_lookup` (raw-SQL managed, already in `include_object`).
- Produces: `hpo_terms_lookup.allowed_modifiers text[]`, and `GET /api/v2/ontology/laterality-policy` → `{"data": [{"hpo_id": str, "allowed_modifiers": [str]}]}`. Task 9 validates against the column; Task 12 allowlists the path.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_laterality_policy.py`:

```python
"""Per-term laterality policy (spec §4.4)."""

import pytest
from sqlalchemy import text

BILATERAL, UNILATERAL, LEFT, RIGHT = (
    "HP:0012832", "HP:0012833", "HP:0012835", "HP:0012834",
)
FULL = {BILATERAL, UNILATERAL, LEFT, RIGHT}

FULL_LATERALITY_TERMS = [
    "HP:0000107",  # Renal cyst
    "HP:0000003",  # Multicystic kidney dysplasia
    "HP:0000089",  # Renal hypoplasia
    "HP:0033132",  # Renal cortical hyperechogenicity
    "HP:0000079",  # Abnormality of the urinary system
]


@pytest.mark.parametrize("hpo_id", FULL_LATERALITY_TERMS)
@pytest.mark.asyncio
async def test_full_laterality_terms(db_session, hpo_id):
    result = await db_session.execute(
        text("SELECT allowed_modifiers FROM hpo_terms_lookup WHERE hpo_id = :id"),
        {"id": hpo_id},
    )
    row = result.first()
    assert row is not None, f"{hpo_id} missing from hpo_terms_lookup"
    assert set(row[0]) == FULL


@pytest.mark.asyncio
async def test_unilateral_renal_agenesis_rejects_bilateral_only(db_session):
    """HP:0000122 already asserts unilaterality, so Bilateral contradicts the term.

    Unilateral is redundant here but NOT rejected: 20 source rows record
    'unilateral unspecified' on this term, and dropping them would leave those
    features with no modifier — indistinguishable from 'laterality never stated',
    the defect of docs/ontology-defect-report-2026-07-30.md §3.
    """
    result = await db_session.execute(
        text("SELECT allowed_modifiers FROM hpo_terms_lookup WHERE hpo_id = 'HP:0000122'")
    )
    assert set(result.scalar_one()) == {UNILATERAL, LEFT, RIGHT}
    assert BILATERAL not in set(result.scalar_one())


@pytest.mark.asyncio
async def test_other_terms_admit_no_modifiers(db_session):
    result = await db_session.execute(
        text("SELECT allowed_modifiers FROM hpo_terms_lookup WHERE hpo_id = 'HP:0004904'")
    )
    assert result.scalar_one() == []


@pytest.mark.asyncio
async def test_endpoint_lists_only_terms_with_modifiers(async_client):
    response = await async_client.get("/api/v2/ontology/laterality-policy")
    assert response.status_code == 200
    policy = {item["hpo_id"]: set(item["allowed_modifiers"]) for item in response.json()["data"]}

    assert policy["HP:0000107"] == FULL
    assert policy["HP:0000122"] == {UNILATERAL, LEFT, RIGHT}
    assert "HP:0004904" not in policy, "terms admitting no modifiers are omitted"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_laterality_policy.py -q`
Expected: FAIL — column `allowed_modifiers` does not exist.

- [ ] **Step 3: Write the migration**

Create `backend/alembic/versions/c8f1a3d5e207_add_hpo_allowed_modifiers.py`:

```python
"""Add per-term laterality policy to hpo_terms_lookup.

Which HPO modifiers a term admits is reference data rather than a constant,
because of one asymmetry: HP:0000122 Unilateral renal agenesis already asserts
unilaterality, so it must reject Bilateral as contradictory. Unilateral is
redundant there but permitted -- see the amendment note in the task body.

Revision ID: c8f1a3d5e207
Revises: a1c4e7f20b93
"""

from alembic import op

revision = "c8f1a3d5e207"
down_revision = "a1c4e7f20b93"
branch_labels = None
depends_on = None

BILATERAL = "HP:0012832"
UNILATERAL = "HP:0012833"
LEFT = "HP:0012835"
RIGHT = "HP:0012834"

FULL_LATERALITY = (BILATERAL, UNILATERAL, LEFT, RIGHT)
# HP:0000122 already asserts unilaterality, so Bilateral contradicts the term.
# Unilateral is redundant but permitted: 20 source rows state "unilateral
# unspecified" on it, and rejecting them would discard a curator's explicit
# annotation (defect report §3). See the amendment note at the top of Task 7.
NOT_BILATERAL = (UNILATERAL, LEFT, RIGHT)

POLICY = {
    "HP:0000107": FULL_LATERALITY,  # Renal cyst
    "HP:0000003": FULL_LATERALITY,  # Multicystic kidney dysplasia
    "HP:0000089": FULL_LATERALITY,  # Renal hypoplasia
    "HP:0033132": FULL_LATERALITY,  # Renal cortical hyperechogenicity
    "HP:0000079": FULL_LATERALITY,  # Abnormality of the urinary system
    "HP:0000122": NOT_BILATERAL,  # Unilateral renal agenesis
}

# These ID literals are deliberately redeclared inline rather than imported from
# migration/phenopackets/laterality.py. A migration must be a frozen snapshot:
# importing a mutable application constant would mean that editing that module
# later silently changes what this revision does on a fresh database.


def upgrade() -> None:
    op.execute(
        "ALTER TABLE hpo_terms_lookup "
        "ADD COLUMN allowed_modifiers text[] NOT NULL DEFAULT '{}'"
    )
    for hpo_id, modifiers in POLICY.items():
        literal = ",".join(f'"{m}"' for m in modifiers)
        op.execute(
            f"UPDATE hpo_terms_lookup SET allowed_modifiers = '{{{literal}}}' "  # noqa: S608
            f"WHERE hpo_id = '{hpo_id}'"
        )


def downgrade() -> None:
    op.execute("ALTER TABLE hpo_terms_lookup DROP COLUMN IF EXISTS allowed_modifiers")
```

- [ ] **Step 4: Add the endpoint**

Append to `backend/app/ontology/routers.py`:

```python
@router.get("/laterality-policy")
async def get_laterality_policy(db: AsyncSession = Depends(get_db)):
    """Get the HPO modifiers each phenotype term admits.

    Only terms that admit at least one modifier are returned; every other term
    admits none. Consumed by the curation console to decide whether to render a
    laterality control, and by the domain validator on the write path.
    """
    query = text(
        """SELECT hpo_id, allowed_modifiers
           FROM hpo_terms_lookup
           WHERE cardinality(allowed_modifiers) > 0
           ORDER BY hpo_id"""
    )
    result = await db.execute(query)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}
```

- [ ] **Step 5: Run migration and tests**

Run: `cd backend && uv run alembic upgrade head && uv run pytest tests/test_laterality_policy.py tests/test_alembic_env_autogenerate.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd backend && uv run ruff format && cd ..
git add backend/alembic/versions/c8f1a3d5e207_add_hpo_allowed_modifiers.py backend/app/ontology/routers.py backend/tests/test_laterality_policy.py
git commit -m "feat(curation): add per-term laterality policy and endpoint

hpo_terms_lookup.allowed_modifiers plus GET /ontology/laterality-policy.
Reference data rather than a constant because HP:0000122 Unilateral renal
agenesis already asserts unilaterality, so it must reject Bilateral as
contradictory. Unilateral stays permitted: 20 source rows state "unilateral
unspecified" on that term and dropping them would discard a curated annotation.

Refs: docs/superpowers/specs/2026-07-30-curation-data-model-design.md §4.4"
```

---

## Task 8: Declare `hnf1bCuration` in the phenopacket schema

A namespaced top-level block for case-level curated facts. It lives inside the JSONB — not a side table — so it inherits revisioning, audit, draft/publish isolation and the existing `revision` optimistic lock for free.

`additionalProperties: false` applies **inside the block only**. The phenopacket top level stays permissive; tightening it is conformance-program work (ADR 0003) and would reject legacy shapes.

**Files:**
- Modify: `backend/app/phenopackets/validation/schema_validator.py:73-88`
- Test: `backend/tests/test_hnf1b_curation_schema.py` (create)

**Interfaces:**
- Consumes: **Task 1 is a hard dependency.** Step 4 constrains `moleculeContext` to the GA4GH enum; the unfixed form writes a VEP consequence there (`VariantAnnotationForm.vue:253`), so doing this first would make every save from the current UI fail validation. Do not reorder.
- Produces: schema acceptance of `phenopacket.hnf1bCuration = {cohort?, familyHistory?, detectionMethod?, curatedBy?, curatedAt?}`. Task 9 validates its *values*; Task 10 strips it on conformant export.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_hnf1b_curation_schema.py`:

```python
"""Schema declaration for the hnf1bCuration block (spec §4.1)."""

import pytest

from app.phenopackets.validation.schema_validator import SchemaValidator

MINIMAL = {
    "id": "phenopacket-940",
    "subject": {"id": "940", "sex": "FEMALE"},
    "metaData": {
        "created": "2026-07-30T00:00:00Z",
        "createdBy": "test",
        "resources": [{"id": "hp", "name": "HPO", "namespacePrefix": "HP"}],
    },
}


@pytest.fixture
def validator():
    return SchemaValidator()


def with_curation(**block):
    return {**MINIMAL, "hnf1bCuration": block}


def test_accepts_a_full_curation_block(validator):
    errors = validator.validate(
        with_curation(
            cohort="fetus",
            familyHistory="positive",
            detectionMethod="mlpa",
            curatedBy="Bernt Popp",
            curatedAt="2026-07-30T14:02:11Z",
        )
    )
    assert errors == []


def test_accepts_a_partial_block(validator):
    """Absence means 'not yet curated' and must stay expressible."""
    assert validator.validate(with_curation(cohort="born")) == []


def test_accepts_a_phenopacket_with_no_curation_block(validator):
    """All 923 legacy records have no block; none may become invalid."""
    assert validator.validate(MINIMAL) == []


def test_rejects_an_unknown_key_inside_the_block(validator):
    errors = validator.validate(with_curation(cohort="born", cohorrt="fetus"))
    assert errors, "additionalProperties:false must apply inside the block"


def test_rejects_a_non_string_field(validator):
    assert validator.validate(with_curation(cohort=42))


def test_top_level_stays_permissive(validator):
    """Tightening the top level is conformance work; legacy shapes must pass."""
    assert validator.validate({**MINIMAL, "someLegacyKey": {"a": 1}}) == []


def _with_molecule_context(value):
    return {
        **MINIMAL,
        "interpretations": [
            {
                "id": "interpretation-001",
                "progressStatus": "IN_PROGRESS",
                "diagnosis": {
                    "genomicInterpretations": [
                        {
                            "subjectOrBiosampleId": "940",
                            "interpretationStatus": "UNKNOWN",
                            "variantInterpretation": {
                                "variationDescriptor": {
                                    "id": "var:x",
                                    "moleculeContext": value,
                                }
                            },
                        }
                    ]
                },
            }
        ],
    }


@pytest.mark.parametrize(
    "value", ["genomic", "transcript", "protein", "unspecified_molecule_context"]
)
def test_accepts_every_ga4gh_molecule_context(validator, value):
    assert validator.validate(_with_molecule_context(value)) == []


def test_rejects_a_vep_consequence_as_molecule_context(validator):
    """The B1 defect: the writer put 'missense_variant' in an enum field."""
    assert validator.validate(_with_molecule_context("missense_variant"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_hnf1b_curation_schema.py -q`
Expected: FAIL on `test_rejects_an_unknown_key_inside_the_block` — the block is currently unconstrained, so a typo passes.

- [ ] **Step 3: Declare the block**

In `backend/app/phenopackets/validation/schema_validator.py`, add to `properties` after `metaData` (around line 88):

```python
                "hnf1bCuration": {
                    "type": "object",
                    "description": (
                        "HNF1B-DB curated case-level facts. Namespaced and "
                        "explicitly NOT GA4GH content: conformant export strips "
                        "it. Stored inside the phenopacket so it inherits "
                        "revisioning, audit and the optimistic lock. Values are "
                        "checked against reference tables by the async domain "
                        "validator, not here."
                    ),
                    "additionalProperties": False,
                    "properties": {
                        "cohort": {"type": "string"},
                        "familyHistory": {"type": "string"},
                        "detectionMethod": {"type": "string"},
                        "curatedBy": {"type": "string"},
                        "curatedAt": {"type": "string"},
                    },
                },
```

- [ ] **Step 4: Constrain `moleculeContext` to the GA4GH enum**

Task 1 stopped the *writer* from putting a VEP consequence there; this stops the
schema from accepting one. The enum includes `unspecified_molecule_context`, which
GA4GH documents as the default — omitting it would reject valid documents.

In the same file, replace the `moleculeContext` declaration at line 207:

```python
                                        "moleculeContext": {
                                            "type": "string",
                                            "enum": [
                                                "unspecified_molecule_context",
                                                "genomic",
                                                "transcript",
                                                "protein",
                                            ],
                                        },
```

- [ ] **Step 5: Confirm the 424 corpus records still validate**

The corpus uses `moleculeContext: "genomic"` in 424 records and omits it in 440.
Both must pass:

```bash
psql -h localhost -p 5433 -U hnf1b_user -d hnf1b_phenopackets -tAc "
SELECT DISTINCT gi->'variantInterpretation'->'variationDescriptor'->>'moleculeContext'
FROM phenopackets p, jsonb_array_elements(p.phenopacket->'interpretations') i,
     jsonb_array_elements(i->'diagnosis'->'genomicInterpretations') gi;"
```

Expected: only `genomic` and an empty line (the omitted case). If any other value
appears, the enum would reject existing data — stop and widen it rather than
breaking the additive-only constraint.

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_hnf1b_curation_schema.py -q`
Expected: PASS, 12 tests.

- [ ] **Step 7: Confirm no existing test regressed**

Run: `cd backend && uv run pytest tests/ -q -k "phenopacket or schema or valid"`
Expected: PASS — the change is additive at the top level, and the `moleculeContext`
enum admits every value the corpus uses.

- [ ] **Step 8: Commit**

```bash
cd backend && uv run ruff format && cd ..
git add backend/app/phenopackets/validation/schema_validator.py backend/tests/test_hnf1b_curation_schema.py
git commit -m "feat(curation): declare hnf1bCuration and constrain moleculeContext

Namespaced top-level object for case-level curated facts, with
additionalProperties:false INSIDE the block so a typo is caught immediately.
The phenopacket top level stays permissive — tightening it is conformance-
program work and would reject legacy shapes.

Living in the JSONB rather than a side table means curation inherits
revisioning, audit, draft/publish isolation and the existing optimistic lock.

moleculeContext is constrained to the GA4GH enum including
unspecified_molecule_context, closing B1 on the read side after Task 1 closed
it on the write side. All 424 corpus records using it say 'genomic'.

Refs: docs/superpowers/specs/2026-07-30-curation-data-model-design.md §4.1, §4.7"
```

---

## Task 9: Async domain validator on the REST write path

Reference-table membership and per-term laterality need database lookups, so they cannot live in the synchronous `Draft7Validator`. A separate async validator runs on the REST write path.

**Scope is deliberately "the REST write path", not "everywhere."** Of the four writers, the two maintenance scripts cannot produce these fields at all; bulk import can and is a documented trusted caller.

**Files:**
- Create: `backend/app/phenopackets/validation/domain.py`
- Modify: `backend/app/phenopackets/services/phenopacket_service.py:143-147`
- Modify: `backend/app/phenopackets/routers/crud.py:449-455`
- Test: `backend/tests/test_domain_validator.py` (create)

**Interfaces:**
- Consumes: Task 5's four tables, Task 7's `allowed_modifiers`, Task 8's schema.
- Produces: `async DomainValidator(db).validate(phenopacket: dict) -> list[str]`, returning human-readable messages. Empty list means valid. Raised to the caller as HTTP 400 with `{"detail": {"validation_errors": [...]}}`, matching `crud.py:448`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_domain_validator.py`:

```python
"""Async domain validation for curation fields (spec §4.5)."""

import pytest

from app.phenopackets.validation.domain import DomainValidator

BILATERAL, UNILATERAL, LEFT = "HP:0012832", "HP:0012833", "HP:0012835"


def packet(**overrides):
    return {
        "id": "phenopacket-940",
        "subject": {"id": "940", "sex": "FEMALE"},
        "metaData": {"created": "2026-07-30T00:00:00Z", "createdBy": "t", "resources": [{"id": "hp", "name": "HPO", "namespacePrefix": "HP"}]},
        **overrides,
    }


def feature(hpo_id, modifiers=None):
    f = {"type": {"id": hpo_id, "label": "x"}, "excluded": False}
    if modifiers is not None:
        f["modifiers"] = [{"id": m} for m in modifiers]
    return f


@pytest.mark.asyncio
async def test_accepts_valid_curation(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(hnf1bCuration={"cohort": "fetus", "detectionMethod": "mlpa"})
    )
    assert errors == []


@pytest.mark.asyncio
async def test_rejects_unknown_enum_value(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(hnf1bCuration={"detectionMethod": "telepathy"})
    )
    assert len(errors) == 1
    assert "detectionMethod" in errors[0] and "telepathy" in errors[0]
    assert "mlpa" in errors[0], "the message should name the allowed values"


@pytest.mark.asyncio
async def test_rejects_unknown_segregation_origin(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(
            interpretations=[
                {
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "variationDescriptor": {
                                        "id": "var:x",
                                        "extensions": [
                                            {"name": "segregation", "value": {"origin": "guessed"}}
                                        ],
                                    }
                                }
                            }
                        ]
                    }
                }
            ]
        )
    )
    assert len(errors) == 1
    assert "segregation" in errors[0]


@pytest.mark.asyncio
async def test_accepts_allowed_laterality(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(phenotypicFeatures=[feature("HP:0000107", [BILATERAL])])
    )
    assert errors == []


@pytest.mark.asyncio
async def test_rejects_bilateral_with_unilateral(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(phenotypicFeatures=[feature("HP:0000107", [BILATERAL, UNILATERAL])])
    )
    assert len(errors) == 1
    assert BILATERAL in errors[0] and UNILATERAL in errors[0]


@pytest.mark.asyncio
async def test_rejects_modifier_outside_the_terms_set(db_session):
    """HP:0000122 already asserts unilaterality, so Bilateral contradicts it."""
    errors = await DomainValidator(db_session).validate(
        packet(phenotypicFeatures=[feature("HP:0000122", [BILATERAL])])
    )
    assert len(errors) == 1
    assert "HP:0000122" in errors[0]


@pytest.mark.asyncio
async def test_accepts_side_only_modifier_on_that_term(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(phenotypicFeatures=[feature("HP:0000122", [LEFT])])
    )
    assert errors == []


@pytest.mark.asyncio
async def test_rejects_modifiers_on_a_term_that_admits_none(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(phenotypicFeatures=[feature("HP:0004904", [BILATERAL])])
    )
    assert len(errors) == 1


@pytest.mark.asyncio
async def test_no_curation_and_no_modifiers_is_valid(db_session):
    """Every one of the 923 legacy records must still pass."""
    assert await DomainValidator(db_session).validate(packet()) == []


@pytest.mark.asyncio
async def test_reports_every_problem_not_just_the_first(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(
            hnf1bCuration={"cohort": "nope", "familyHistory": "maybe"},
            phenotypicFeatures=[feature("HP:0004904", [BILATERAL])],
        )
    )
    assert len(errors) == 3


def _packet_with_extension_value(value):
    return packet(
        interpretations=[
            {
                "diagnosis": {
                    "genomicInterpretations": [
                        {
                            "variantInterpretation": {
                                "variationDescriptor": {
                                    "id": "var:x",
                                    "extensions": [{"name": "segregation", "value": value}],
                                }
                            }
                        }
                    ]
                }
            }
        ]
    )


@pytest.mark.parametrize("value", ["de_novo", ["de_novo"], 42, None])
@pytest.mark.asyncio
async def test_malformed_segregation_value_is_a_validation_error_not_a_crash(
    db_session, value
):
    """The schema does not constrain extension values, so anything can arrive.

    An AttributeError here would surface as HTTP 500 instead of the 400 the
    contract promises.
    """
    errors = await DomainValidator(db_session).validate(_packet_with_extension_value(value))
    assert errors and "segregation" in errors[0]


@pytest.mark.asyncio
async def test_segregation_extension_without_origin_is_ignored(db_session):
    """An object with no origin states nothing; that is not an error."""
    assert await DomainValidator(db_session).validate(_packet_with_extension_value({})) == []


@pytest.mark.parametrize(
    "malformed",
    [
        {"interpretations": "not-a-list"},
        {"interpretations": [{"diagnosis": {"genomicInterpretations": "nope"}}]},
        {"phenotypicFeatures": "not-a-list"},
    ],
)
@pytest.mark.asyncio
async def test_structurally_malformed_documents_do_not_crash(db_session, malformed):
    await DomainValidator(db_session).validate(packet(**malformed))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_domain_validator.py -q`
Expected: FAIL — `app.phenopackets.validation.domain` does not exist.

- [ ] **Step 3: Implement the validator**

Create `backend/app/phenopackets/validation/domain.py`:

```python
"""Database-backed validation for curated fields.

Reference-table membership and per-term laterality both require lookups, so
they cannot live in the synchronous ``Draft7Validator`` in ``schema_validator``.
This validator runs on the REST write path only (spec §4.5): of the four
writers, the two maintenance scripts cannot produce these fields, and bulk
import is a documented trusted caller.
"""

from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

BILATERAL = "HP:0012832"
UNILATERAL = "HP:0012833"
LEFT = "HP:0012835"
RIGHT = "HP:0012834"
_SIDED = {UNILATERAL, LEFT, RIGHT}


def _as_list(value: Any) -> List[Any]:
    """Return ``value`` if it is a list, else an empty list.

    Curated JSONB reaches this module before the schema constrains these
    sub-structures, so a scalar where a list belongs must degrade to "nothing to
    check" rather than raising.
    """
    return value if isinstance(value, list) else []

# hnf1bCuration field -> reference table backing it.
_CURATION_FIELDS = {
    "cohort": "cohort_values",
    "familyHistory": "family_history_values",
    "detectionMethod": "detection_method_values",
}


class DomainValidator:
    """Validate curated values against reference data."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def validate(self, phenopacket: Dict[str, Any]) -> List[str]:
        """Return human-readable problems; empty list means valid."""
        errors: List[str] = []
        errors.extend(await self._validate_curation(phenopacket))
        errors.extend(await self._validate_segregation(phenopacket))
        errors.extend(await self._validate_laterality(phenopacket))
        return errors

    async def _allowed(self, table: str) -> List[str]:
        result = await self._db.execute(
            text(f"SELECT value FROM {table} ORDER BY sort_order")  # noqa: S608
        )
        return [row[0] for row in result.fetchall()]

    async def _validate_curation(self, phenopacket: Dict[str, Any]) -> List[str]:
        block = phenopacket.get("hnf1bCuration") or {}
        errors = []
        for field, table in _CURATION_FIELDS.items():
            value = block.get(field)
            if value is None:
                continue
            allowed = await self._allowed(table)
            if value not in allowed:
                errors.append(
                    f"hnf1bCuration.{field}: {value!r} is not a valid value. "
                    f"Allowed: {', '.join(allowed)}"
                )
        return errors

    async def _validate_segregation(self, phenopacket: Dict[str, Any]) -> List[str]:
        """Collect segregation origins, tolerating malformed input.

        The JSON schema does not declare ``variationDescriptor.extensions`` or its
        value shape, so a string, a list, or a missing ``origin`` all reach this
        method. Every access is type-checked: an ``AttributeError`` here would
        surface as HTTP 500 instead of the 400 the contract promises.
        """
        errors: List[str] = []
        origins: List[Any] = []

        for interp in _as_list(phenopacket.get("interpretations")):
            diagnosis = interp.get("diagnosis") if isinstance(interp, dict) else None
            genomic = _as_list((diagnosis or {}).get("genomicInterpretations"))
            for gi in genomic:
                if not isinstance(gi, dict):
                    continue
                vi = gi.get("variantInterpretation")
                descriptor = (vi or {}).get("variationDescriptor") if isinstance(vi, dict) else None
                for ext in _as_list((descriptor or {}).get("extensions")):
                    if not isinstance(ext, dict) or ext.get("name") != "segregation":
                        continue
                    value = ext.get("value")
                    if not isinstance(value, dict):
                        errors.append(
                            "segregation: extension value must be an object with an "
                            f"'origin' key, got {type(value).__name__}"
                        )
                        continue
                    origins.append(value.get("origin"))

        stated = [o for o in origins if o is not None]
        if not stated:
            return errors

        allowed = await self._allowed("segregation_values")
        errors.extend(
            f"segregation.origin: {origin!r} is not a valid value. "
            f"Allowed: {', '.join(allowed)}"
            for origin in stated
            if origin not in allowed
        )
        return errors

    async def _validate_laterality(self, phenopacket: Dict[str, Any]) -> List[str]:
        features = phenopacket.get("phenotypicFeatures") or []
        annotated = [
            (f.get("type", {}).get("id"), [m.get("id") for m in (f.get("modifiers") or [])])
            for f in features
            if f.get("modifiers")
        ]
        if not annotated:
            return []

        result = await self._db.execute(
            text(
                "SELECT hpo_id, allowed_modifiers FROM hpo_terms_lookup "
                "WHERE hpo_id = ANY(:ids)"
            ),
            {"ids": [hpo_id for hpo_id, _ in annotated]},
        )
        policy = {row[0]: set(row[1] or []) for row in result.fetchall()}

        errors = []
        for hpo_id, modifiers in annotated:
            allowed = policy.get(hpo_id, set())
            applied = set(modifiers)

            if BILATERAL in applied and applied & _SIDED:
                conflicting = ", ".join(sorted(applied & _SIDED))
                errors.append(
                    f"{hpo_id}: {BILATERAL} (Bilateral) cannot be combined with "
                    f"{conflicting}"
                )
                continue

            outside = applied - allowed
            if outside:
                allowed_text = ", ".join(sorted(allowed)) if allowed else "none"
                errors.append(
                    f"{hpo_id}: modifier(s) {', '.join(sorted(outside))} not permitted. "
                    f"Allowed: {allowed_text}"
                )
        return errors
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_domain_validator.py -q`
Expected: PASS, 10 tests.

- [ ] **Step 5: Wire it into the create path**

In `backend/app/phenopackets/services/phenopacket_service.py`, replace lines 143-147:

```python
        sanitized = self._sanitizer.sanitize_phenopacket(payload.phenopacket)
        errors = self._validator.validate(sanitized)
        if errors:
            raise ServiceValidationError(errors)

        # Reference-data checks that need the database (spec §4.5).
        domain_errors = await DomainValidator(self._repo.session).validate(sanitized)
        if domain_errors:
            raise ServiceValidationError(domain_errors)
```

with the import at the top of the module:

```python
from app.phenopackets.validation.domain import DomainValidator
```

- [ ] **Step 6: Wire it into the edit path**

In `backend/app/phenopackets/routers/crud.py`, after line 455:

```python
    sanitized = sanitizer.sanitize_phenopacket(phenopacket_data.phenopacket)
    errors = validator.validate(sanitized)
    if errors:
        raise HTTPException(status_code=400, detail={"validation_errors": errors})

    domain_errors = await DomainValidator(db).validate(sanitized)
    if domain_errors:
        raise HTTPException(status_code=400, detail={"validation_errors": domain_errors})
```

with the import at the top:

```python
from app.phenopackets.validation.domain import DomainValidator
```

- [ ] **Step 7: Write the end-to-end rejection test**

Append to `backend/tests/test_domain_validator.py`:

```python
@pytest.mark.asyncio
async def test_rest_create_rejects_invalid_curation_with_400(async_client, curator_headers):
    response = await async_client.post(
        "/api/v2/phenopackets/",
        json={"phenopacket": packet(hnf1bCuration={"cohort": "nope"})},
        headers=curator_headers,
    )
    assert response.status_code == 400
    assert "cohort" in str(response.json()["detail"])


@pytest.mark.asyncio
async def test_rest_create_accepts_valid_curation(async_client, curator_headers):
    response = await async_client.post(
        "/api/v2/phenopackets/",
        json={"phenopacket": packet(hnf1bCuration={"cohort": "fetus"})},
        headers=curator_headers,
    )
    assert response.status_code in (200, 201)
```

`curator_headers` (`backend/tests/conftest.py:384`) is required here, **not**
`auth_headers` (`:356`) — the latter authenticates `test_user`, whose role is
`viewer` (`:209`), and `POST /phenopackets/` is gated by `require_curator`
(`crud.py:382`), so a viewer receives 403 before validation ever runs.

Note also that `resources` must be non-empty: the sanitizer strips empty arrays
(`sanitizer.py:29`) and the schema then rejects the record for the missing required
`metaData.resources` field (`schema_validator.py:73`) — masking the domain error the
test is trying to observe.

- [ ] **Step 8: Run the whole backend suite**

Run: `cd backend && uv run ruff format && uv run ruff check . && uv run pytest -q`
Expected: PASS. Note `.env` must not set `ENABLE_DEV_AUTH` — it breaks `make check`.

- [ ] **Step 9: Commit**

```bash
git add backend/app/phenopackets/validation/domain.py backend/app/phenopackets/services/phenopacket_service.py backend/app/phenopackets/routers/crud.py backend/tests/test_domain_validator.py
git commit -m "feat(curation): validate curation values and laterality on the write path

Reference-table membership and per-term laterality need DB lookups, so they
cannot live in the synchronous Draft7Validator. Scope is the REST write path:
the two maintenance scripts cannot produce these fields, and bulk import is a
documented trusted caller.

Errors are HTTP 400 with {validation_errors: [...]}, matching crud.py:448.

Refs: docs/superpowers/specs/2026-07-30-curation-data-model-design.md §4.5"
```

---

## Task 10: Server-side export with `conformant` and `full` modes

`hnf1bCuration` is HNF1B-DB curation metadata, so a conformant export omits it. The current frontend download just serializes whatever it fetched, so there is no server-side export to extend — this adds one.

`conformant` is **not** a claim of GA4GH validity: the corpus retains the ADR 0003 debts. It means only that HNF1B-specific curation has been stripped. The docstring and the OpenAPI description must both say so.

**Files:**
- Modify: `backend/app/phenopackets/routers/crud.py`
- Test: `backend/tests/test_phenopacket_export.py` (create)

**Interfaces:**
- Consumes: Task 8's block.
- Produces: `GET /api/v2/phenopackets/{phenopacket_id}/export?mode={conformant|full}` → the phenopacket document. Task 12 allowlists the path for MCP.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_phenopacket_export.py`:

```python
"""Export modes (spec §4.6)."""

import pytest

CURATION = {"cohort": "fetus", "detectionMethod": "mlpa"}


@pytest.fixture
async def curated_phenopacket_id(async_client, curator_headers):
    payload = {
        "phenopacket": {
            "id": "phenopacket-export-test",
            "subject": {"id": "export-test", "sex": "FEMALE"},
            "metaData": {
                "created": "2026-07-30T00:00:00Z",
                "createdBy": "test",
                "resources": [{"id": "hp", "name": "HPO", "namespacePrefix": "HP"}],
            },
            "hnf1bCuration": CURATION,
        }
    }
    response = await async_client.post(
        "/api/v2/phenopackets/", json=payload, headers=curator_headers
    )
    assert response.status_code in (200, 201)
    return "phenopacket-export-test"


@pytest.mark.asyncio
async def test_full_mode_includes_curation(async_client, curated_phenopacket_id):
    response = await async_client.get(
        f"/api/v2/phenopackets/{curated_phenopacket_id}/export?mode=full"
    )
    assert response.status_code == 200
    assert response.json()["hnf1bCuration"] == CURATION


@pytest.mark.asyncio
async def test_conformant_mode_strips_curation(async_client, curated_phenopacket_id):
    response = await async_client.get(
        f"/api/v2/phenopackets/{curated_phenopacket_id}/export?mode=conformant"
    )
    assert response.status_code == 200
    assert "hnf1bCuration" not in response.json()


@pytest.mark.asyncio
async def test_conformant_is_the_default(async_client, curated_phenopacket_id):
    response = await async_client.get(
        f"/api/v2/phenopackets/{curated_phenopacket_id}/export"
    )
    assert "hnf1bCuration" not in response.json()


@pytest.mark.asyncio
async def test_the_two_modes_differ_only_by_that_key(async_client, curated_phenopacket_id):
    full = (
        await async_client.get(
            f"/api/v2/phenopackets/{curated_phenopacket_id}/export?mode=full"
        )
    ).json()
    conformant = (
        await async_client.get(
            f"/api/v2/phenopackets/{curated_phenopacket_id}/export?mode=conformant"
        )
    ).json()

    assert {k: v for k, v in full.items() if k != "hnf1bCuration"} == conformant


@pytest.mark.asyncio
async def test_unknown_mode_is_rejected(async_client, curated_phenopacket_id):
    response = await async_client.get(
        f"/api/v2/phenopackets/{curated_phenopacket_id}/export?mode=pretty"
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_missing_record_is_404(async_client):
    response = await async_client.get("/api/v2/phenopackets/does-not-exist/export")
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_phenopacket_export.py -q`
Expected: FAIL with 404 — the route does not exist.

- [ ] **Step 3: Read how the detail GET enforces visibility**

Run: `sed -n '1,120p' backend/app/phenopackets/repositories/visibility.py` and find the
detail `GET /{phenopacket_id}` handler in `crud.py`.

Two things matter and must be mirrored exactly, or export becomes a hole in the
publication model:

- `public_filter` (`visibility.py:26`) restricts which records an anonymous or
  viewer user may see at all.
- `visibility.py:80` dereferences `head_published_revision.content_jsonb` during an
  active edit, so public reads never observe unpublished working-copy changes.

Reading `pp.phenopacket` directly would export a curator's in-progress draft to an
anonymous caller.

- [ ] **Step 4: Add the route with the same visibility boundary**

Append to `backend/app/phenopackets/routers/crud.py`, using the same optional-user
dependency and content-selection helper the detail GET uses (substitute the real
names found in Step 3):

```python
@router.get("/{phenopacket_id}/export")
async def export_phenopacket(
    phenopacket_id: str,
    mode: Literal["conformant", "full"] = "conformant",
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    """Export one phenopacket document.

    Visibility matches the detail endpoint exactly: anonymous and viewer callers
    see published content only, dereferenced through head_published_revision, so
    an in-progress draft is never exported.

    ``full`` additionally returns the ``hnf1bCuration`` block and therefore
    requires curator access — it is internal curation metadata.

    ``conformant`` (default) removes that block. It is **not** a claim of GA4GH
    Phenopackets v2 validity: the corpus retains the nonconformances recorded in
    docs/adr/0003-ga4gh-conformance-debt.md.
    """
    repo = PhenopacketRepository(db)
    pp = await repo.get_visible_by_id(phenopacket_id, user=current_user)
    if pp is None:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    if mode == "full" and not user_is_curator(current_user):
        raise HTTPException(
            status_code=403,
            detail="full export requires curator access",
        )

    document = dict(resolve_visible_content(pp, user=current_user))
    if mode == "conformant":
        document.pop("hnf1bCuration", None)
    return document
```

Add `Literal` to the module's `typing` import if absent. If the repository has no
`get_visible_by_id`/`resolve_visible_content` equivalent, reuse whatever the detail
GET calls rather than inventing a parallel path — a second, subtly different
visibility implementation is exactly the defect this step exists to avoid.

- [ ] **Step 5: Add the leakage tests**

Append to `backend/tests/test_phenopacket_export.py`, using the existing
`draft_record` (`conftest.py:502`), `published_record` (`:526`) and
`clone_in_progress_record` (`:570`) fixtures:

```python
@pytest.mark.asyncio
async def test_anonymous_cannot_export_a_draft(async_client, draft_record):
    response = await async_client.get(
        f"/api/v2/phenopackets/{draft_record.phenopacket_id}/export"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_anonymous_export_of_a_record_being_edited_returns_published_content(
    async_client, clone_in_progress_record
):
    """The working copy has unpublished edits; the export must not show them."""
    response = await async_client.get(
        f"/api/v2/phenopackets/{clone_in_progress_record.phenopacket_id}/export"
    )
    assert response.status_code == 200
    # Assert against the published revision's content, not pp.phenopacket.


@pytest.mark.asyncio
async def test_full_mode_requires_curator(async_client, published_record):
    response = await async_client.get(
        f"/api/v2/phenopackets/{published_record.phenopacket_id}/export?mode=full"
    )
    assert response.status_code in (401, 403)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_phenopacket_export.py -q`
Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
cd backend && uv run ruff format && cd ..
git add backend/app/phenopackets/routers/crud.py backend/tests/test_phenopacket_export.py
git commit -m "feat(curation): add export with conformant and full modes

conformant (default) strips hnf1bCuration; full returns the document as stored.
conformant is explicitly NOT a claim of GA4GH validity — the corpus retains the
debts in ADR 0003 — only that HNF1B-specific curation has been removed.

Refs: docs/superpowers/specs/2026-07-30-curation-data-model-design.md §4.6"
```

---

## Task 11: Extend the vocabulary composable

`usePhenopacketVocabularies.js` hardcodes five refs, five requests and five return values (`:42-123`). It is extended deliberately rather than made generic — a generic rewrite would have to paper over the four divergent legacy shapes.

**Files:**
- Modify: `frontend/src/composables/usePhenopacketVocabularies.js`
- Test: `frontend/tests/unit/composables/usePhenopacketVocabularies.spec.js` (create or modify)

**Interfaces:**
- Consumes: Task 6's endpoints.
- Produces: `usePhenopacketVocabularies()` additionally returns `cohort`, `detectionMethod`, `segregation`, `familyHistory` refs, each `[{value, label, description}]`. The Phase 3 console binds its selects to these.

- [ ] **Step 1: Read the current composable**

Run: `sed -n '1,124p' frontend/src/composables/usePhenopacketVocabularies.js`

Note the exact ref names, the request helper, the `loadAll` implementation and the returned object, so the four additions match the file's own idiom rather than a guessed one.

- [ ] **Step 2: Write the failing test**

Create `frontend/tests/unit/composables/usePhenopacketVocabularies.spec.js`:

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest';

// The composable imports the NAMED export `apiClient` from '@/api'
// (usePhenopacketVocabularies.js:40), re-exported from src/api/index.js.
// Mocking '@/api/client' would not intercept anything — that module does not exist.
const get = vi.fn();
vi.mock('@/api', () => ({ apiClient: { get } }));

import { usePhenopacketVocabularies } from '@/composables/usePhenopacketVocabularies';

const FIXTURES = {
  '/ontology/vocabularies/cohort': [
    { value: 'born', label: 'Born', description: null },
    { value: 'fetus', label: 'Fetus', description: null },
  ],
  '/ontology/vocabularies/detection-method': [{ value: 'mlpa', label: 'MLPA', description: null }],
  '/ontology/vocabularies/segregation': [
    { value: 'de_novo', label: 'De novo', description: null },
  ],
  '/ontology/vocabularies/family-history': [
    { value: 'positive', label: 'Positive', description: null },
  ],
};

describe('usePhenopacketVocabularies curation additions', () => {
  beforeEach(() => {
    get.mockReset();
    get.mockImplementation((url) => {
      const key = Object.keys(FIXTURES).find((k) => url.includes(k));
      return Promise.resolve({ data: { data: key ? FIXTURES[key] : [] } });
    });
    // loadAll() logs through window.logService (usePhenopacketVocabularies.js:62);
    // without this every test throws on the first log call.
    window.logService = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };
  });

  it('exposes the four curation vocabularies', () => {
    const v = usePhenopacketVocabularies();
    expect(v).toHaveProperty('cohort');
    expect(v).toHaveProperty('detectionMethod');
    expect(v).toHaveProperty('segregation');
    expect(v).toHaveProperty('familyHistory');
  });

  it('populates them from loadAll', async () => {
    const v = usePhenopacketVocabularies();
    await v.loadAll();

    expect(v.cohort.value.map((i) => i.value)).toEqual(['born', 'fetus']);
    expect(v.detectionMethod.value[0].label).toBe('MLPA');
    expect(v.segregation.value[0].value).toBe('de_novo');
    expect(v.familyHistory.value[0].value).toBe('positive');
  });

  it('still loads the five pre-existing vocabularies', async () => {
    const v = usePhenopacketVocabularies();
    await v.loadAll();
    expect(v).toHaveProperty('sex');
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/composables/usePhenopacketVocabularies.spec.js`
Expected: FAIL — the four properties are absent.

- [ ] **Step 4: Add the four vocabularies**

Following the file's existing pattern exactly (read in Step 1), add four refs initialised to `[]`, four fetches inside `loadAll` matching how the existing five are issued, and the four names in the returned object. Add above the new refs:

```javascript
// Curation vocabularies (spec §4.6). Added explicitly rather than by making
// this composable generic: the five pre-existing endpoints have four different
// item shapes, so a generic loader would have to special-case them anyway.
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/composables/usePhenopacketVocabularies.spec.js`
Expected: PASS, 3 tests.

- [ ] **Step 6: Run the full frontend gate**

Run: `cd frontend && npx vitest run && npm run lint:check && npx prettier --check src tests`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/composables/usePhenopacketVocabularies.js frontend/tests/unit/composables/usePhenopacketVocabularies.spec.js
git commit -m "feat(curation): load the four curation vocabularies in the composable

Extended explicitly rather than made generic: the five pre-existing vocabulary
endpoints have four different item shapes, so a generic loader would special-
case them anyway.

Refs: docs/superpowers/specs/2026-07-30-curation-data-model-design.md §4.6"
```

---

## Task 12: Update the MCP read contract

The MCP server is read-only, so there is no write risk — but four new API paths appeared, and `tests/test_contract.py` proves there are no silent allowlist gaps. Without this task the contract test fails.

`/ontology/vocabularies/[a-z-]+` in `allowlist.py:37` already matches the four vocabulary paths. `/ontology/laterality-policy` and `/phenopackets/{id}/export` do **not** match any rule and need explicit decisions.

`hnf1b_resolve_terms`' `vocabulary` `Literal` (`terms.py:36-43`) must gain the four names or the vocabularies are unreachable.

**No change to classification shaping.** ACMG stays in `interpretationStatus` per ADR 0003, so `individuals.py:160` is untouched.

**Files:**
- Modify: `mcp/src/hnf1b_mcp/tools/terms.py:36-43`
- Modify: `mcp/src/hnf1b_mcp/client/allowlist.py`
- Test: `mcp/tests/test_contract.py` (existing, must stay green)

**Interfaces:**
- Consumes: Tasks 6, 7, 10.
- Produces: MCP `hnf1b_resolve_terms(vocabulary=...)` accepting the four new names.

- [ ] **Step 1: Confirm the snapshot already carries the new routes**

Tasks 6, 7 and 10 each refreshed `mcp/contract/openapi.snapshot.json` per the Global
Constraints. Verify before touching the allowlist — if the snapshot is stale, the
contract test reads the *old* path list, the new routes create no detectable gap, and
adding allowlist rules that match nothing fails the test for the opposite reason:

```bash
python3 -c "
import json
paths = json.load(open('mcp/contract/openapi.snapshot.json'))['paths']
for p in sorted(paths):
    if 'laterality' in p or 'export' in p or 'vocabularies' in p:
        print(p)
"
```

Expected: the four `/ontology/vocabularies/...` paths, `/ontology/laterality-policy`,
and `/phenopackets/{phenopacket_id}/export`. If any is missing, go back and run
`cd backend && uv run python scripts/dump_openapi.py` before continuing.

- [ ] **Step 2: Run the contract test to see it fail**

Run: `cd mcp && uv run pytest tests/test_contract.py -q`
Expected: FAIL — `/ontology/laterality-policy` and `/phenopackets/{id}/export` are now in the snapshot but match neither `_RULES` nor `_DENY`, which is exactly the silent gap the test exists to catch.

- [ ] **Step 2: Extend the vocabulary `Literal`**

In `mcp/src/hnf1b_mcp/tools/terms.py`, replace lines 36-43:

```python
        vocabulary: Literal[
            "hpo",
            "sex",
            "interpretation-status",
            "progress-status",
            "allelic-state",
            "evidence-code",
            "cohort",
            "detection-method",
            "segregation",
            "family-history",
        ] = "hpo",
```

- [ ] **Step 3: Allowlist the laterality policy, allowlist export**

In `mcp/src/hnf1b_mcp/client/allowlist.py`, add after the `/ontology/vocabularies/...` rule:

```python
    # Per-term admissible HPO modifiers; read-only reference data.
    (re.compile(r"^/ontology/laterality-policy$"), False),
```

and next to the phenopacket rules, **before** the catch-all `^/phenopackets/[^/]+$` rule (the comment there notes it must stay last among `/phenopackets` rules):

```python
    # Export is a read of a single record; conformant mode is the default.
    (re.compile(r"^/phenopackets/[^/]+/export$"), False),
```

- [ ] **Step 4: Run the contract test**

Run: `cd mcp && uv run pytest tests/test_contract.py -q`
Expected: PASS.

- [ ] **Step 5: Decide MCP response shaping for `hnf1bCuration`**

`mcp/src/hnf1b_mcp/services/individuals.py:219` constructs its output field-by-field,
so `hnf1bCuration` is dropped silently today. Silence is not a decision — make one
explicitly and record it.

Recommended: **exclude it** from MCP output for now, and say why in the service
docstring. The MCP surface is for public consumption, `full` export requires curator
access (Task 10), and curation provenance is not useful to an external agent. Add a
test asserting the exclusion is deliberate:

```python
async def test_mcp_output_excludes_curation_metadata(...):
    """hnf1bCuration is curator-internal; the MCP surface is public.

    Asserted rather than left implicit so that adding it later is a conscious
    contract change, not an accident of field-by-field shaping.
    """
```

Update the `hnf1b_resolve_terms` docstring to list the four new vocabularies.

- [ ] **Step 6: Regenerate the generated models**

Run: `cd mcp && make contract`

This reads the (already-refreshed) snapshot and regenerates `_generated_models.py`.
CI excludes that file from its drift check (`.github/workflows/ci.yml:240`), so verify
by hand:

Run: `git diff --stat mcp/`
Expected: `_generated_models.py` shows the new paths. If it is unchanged while the
snapshot contains them, generation did not run — investigate before committing.

- [ ] **Step 6: Run the whole MCP suite**

Run: `cd mcp && uv run pytest -q`
Expected: PASS.

- [ ] **Step 7: Verify the new vocabularies resolve end-to-end**

With the backend running on :8000:

```bash
curl -s "http://localhost:8000/api/v2/ontology/vocabularies/detection-method" | head -c 400
curl -s "http://localhost:8000/api/v2/ontology/laterality-policy" | head -c 400
```

Expected: `{"data":[{"value":"sanger",...}]}` and a policy list including `HP:0000122` with exactly `["HP:0012833","HP:0012835","HP:0012834"]` (order per the endpoint; Bilateral `HP:0012832` absent).

- [ ] **Step 8: Commit**

```bash
git add mcp/
git commit -m "feat(mcp): allow the curation vocabularies, laterality policy and export

hnf1b_resolve_terms gains cohort/detection-method/segregation/family-history.
laterality-policy and phenopackets/{id}/export are explicitly allowlisted —
without a decision they match neither _RULES nor _DENY and fail the
no-silent-gaps contract test.

Classification shaping is deliberately untouched: ACMG stays in
interpretationStatus per ADR 0003.

Refs: docs/superpowers/specs/2026-07-30-curation-data-model-design.md §4.8"
```

---

## Task 12b: Prove curation inherits the revision machinery

The entire justification for putting `hnf1bCuration` in the JSONB rather than a side
table is that it inherits revisioning, audit, draft/publish isolation and the existing
optimistic lock. Nothing so far tests that claim — Tasks 8-10 only exercise create.

If any assertion here fails, the JSONB placement did not earn its keep and the design
needs revisiting before Phase 3 builds on it.

**Files:**
- Test: `backend/tests/test_curation_revision_semantics.py` (create)

**Interfaces:**
- Consumes: Tasks 8, 9, 10.
- Produces: nothing. This is the gate that validates the spec's central design claim.

- [ ] **Step 1: Read the existing state fixtures and edit flow**

Run: `sed -n '500,610p' backend/tests/conftest.py` and
`grep -n "edit_record\|publish\|def " backend/app/phenopackets/services/state_service.py | head -40`

Use `draft_record` (`:502`), `published_record` (`:526`), `clone_in_progress_record`
(`:570`) and `another_curator` (`:477`) rather than building new fixtures.

- [ ] **Step 2: Write the tests**

Create `backend/tests/test_curation_revision_semantics.py`:

```python
"""hnf1bCuration inherits the revision machinery (spec §2.7, §4.1).

Living in the JSONB rather than a side table is the design's central claim.
These tests are what make it true rather than merely asserted.
"""

import pytest


@pytest.mark.asyncio
async def test_update_round_trips_curation(async_client, curator_headers, draft_record):
    """PUT then GET returns what was written."""


@pytest.mark.asyncio
async def test_absence_and_not_reported_are_distinguishable(
    async_client, curator_headers, draft_record
):
    """NULL/absent means 'not yet curated'; not_reported means 'source is silent'.

    Phase 3's completeness indicator and any later QC queue depend on telling
    these apart through the API, not just in storage.
    """


@pytest.mark.asyncio
async def test_editing_curation_produces_a_revision_containing_the_change(
    db_session, async_client, curator_headers, draft_record
):
    """phenopacket_revisions.content_jsonb must carry the curation edit."""


@pytest.mark.asyncio
async def test_curation_edit_does_not_alter_the_published_head(
    db_session, async_client, curator_headers, published_record
):
    """Editing the working copy must leave head_published_revision untouched."""


@pytest.mark.asyncio
async def test_public_read_during_an_edit_shows_published_curation(
    async_client, clone_in_progress_record
):
    """visibility.py:80 dereferences the published head; curation follows it."""


@pytest.mark.asyncio
async def test_concurrent_curation_edit_returns_409(
    async_client, curator_headers, draft_record
):
    """Two curators, one stale revision -> optimistic lock rejects the second.

    Inherited from Phenopacket.revision at no cost, which a side table would
    have had to reimplement.
    """


@pytest.mark.asyncio
async def test_a_record_with_zero_interpretations_accepts_curation(
    async_client, curator_headers, draft_record
):
    """59 corpus records have no interpretations at all.

    This is why case-level facts are not on variantInterpretation.
    """


@pytest.mark.asyncio
async def test_rollback_restores_prior_curation(
    db_session, async_client, curator_headers, published_record
):
    """Reverting to an earlier revision reverts curation with it."""
```

Fill each body against the real PUT/publish/rollback API discovered in Step 1 —
the docstrings define the required behaviour, not the implementation.

- [ ] **Step 3: Run them**

Run: `cd backend && uv run pytest tests/test_curation_revision_semantics.py -q`
Expected: PASS. A failure here is a design signal, not a test bug — stop and reassess
before continuing to Phase 3.

- [ ] **Step 4: Commit**

```bash
cd backend && uv run ruff format && cd ..
git add backend/tests/test_curation_revision_semantics.py
git commit -m "test(curation): prove hnf1bCuration inherits the revision machinery

The whole reason curation lives in the JSONB rather than a side table is that
it gets revisioning, audit, draft/publish isolation, rollback and the optimistic
lock for free. These tests make that claim checkable.

Refs: docs/superpowers/specs/2026-07-30-curation-data-model-design.md §2.7, §4.1"
```

---

## Task 13: Verify the whole contract end-to-end in the browser

Phase 1 changed what the form writes; Phase 2 added what it can write into. Nothing has yet exercised both together against a real backend.

**Files:**
- Test: `frontend/tests/e2e/curation-contract.spec.js` (create)

**Interfaces:**
- Consumes: everything above.
- Produces: nothing consumed by later tasks. This is the gate before Phase 3 begins.

- [ ] **Step 1: Read the existing Playwright setup before writing anything**

Run: `cat frontend/playwright.config.js` and `ls frontend/tests/e2e/`

Three facts govern this task and contradict the "port 3000" rule that applies to
manual `make frontend` runs:

- `baseURL` is `process.env.E2E_BASE_URL || 'http://localhost:5173'`
  (`playwright.config.js:15,29`), and the config's own `webServer` starts
  `npm run dev -- --port 5173 --strictPort` (`:47`). **Never hardcode a host in the
  spec** — use relative paths so `baseURL` applies.
- `testDir` is `./tests/e2e` (`:19`).
- `/phenopackets/create` requires authentication (`frontend/src/router/index.js:30`).
  Find the existing sign-in helper in `tests/e2e/` (`loginAsAdmin` /
  `primeAuthSession` or equivalent) and reuse it — do not roll a new one.

Also note CI migrates an **empty** database and seeds only an admin
(`.github/workflows/ci.yml:298`), so `phenopacket-219` does not exist there. Every
record this spec needs must be created through the API by the test itself.

- [ ] **Step 2: Start the backend**

Run: `make hybrid-up` then `make backend`. Playwright starts the frontend itself.

`backend/.env` must contain `REDIS_URL=redis://localhost:6380` or the cache silently
degrades.

- [ ] **Step 3: Write the end-to-end check**

Create `frontend/tests/e2e/curation-contract.spec.js`. Substitute the real sign-in
helper name found in Step 1 for `signInAsCurator`, and the real API base the other
e2e specs use for `apiRequest`.

```javascript
import { test, expect } from '@playwright/test';
import { signInAsCurator, apiRequest } from './helpers/auth';

const RESOURCES = [{ id: 'hp', name: 'HPO', namespacePrefix: 'HP' }];

/** Create a record through the API so the test does not depend on seeded data. */
async function createRecord(request, token, overrides = {}) {
  const id = `phenopacket-e2e-${Date.now()}`;
  const response = await apiRequest(request, token).post('/phenopackets/', {
    data: {
      phenopacket: {
        id,
        subject: { id: id.replace('phenopacket-', ''), sex: 'FEMALE' },
        metaData: { created: new Date().toISOString(), createdBy: 'e2e', resources: RESOURCES },
        ...overrides,
      },
    },
  });
  expect(response.ok()).toBeTruthy();
  return id;
}

test.describe('curation storage contract', () => {
  test('the four vocabularies are reachable and correctly shaped', async ({ request }) => {
    for (const name of ['cohort', 'detection-method', 'segregation', 'family-history']) {
      const response = await apiRequest(request).get(`/ontology/vocabularies/${name}`);
      expect(response.ok()).toBeTruthy();

      const { data } = await response.json();
      expect(data.length).toBeGreaterThan(0);
      for (const item of data) {
        expect(Object.keys(item).sort()).toEqual(['description', 'label', 'value']);
      }
    }
  });

  test('laterality policy encodes the HP:0000122 asymmetry', async ({ request }) => {
    const response = await apiRequest(request).get('/ontology/laterality-policy');
    const { data } = await response.json();
    const policy = Object.fromEntries(data.map((i) => [i.hpo_id, i.allowed_modifiers.sort()]));

    expect(policy['HP:0000107']).toEqual(
      ['HP:0012832', 'HP:0012833', 'HP:0012834', 'HP:0012835'].sort()
    );
    expect(policy['HP:0000122']).toEqual(['HP:0012833', 'HP:0012834', 'HP:0012835'].sort());
  });

  test('a curated record round-trips and exports in both modes', async ({ request }) => {
    const token = await signInAsCurator(request);
    const id = await createRecord(request, token, {
      hnf1bCuration: { cohort: 'fetus', detectionMethod: 'mlpa', familyHistory: 'positive' },
    });

    const full = await apiRequest(request, token).get(`/phenopackets/${id}/export?mode=full`);
    expect((await full.json()).hnf1bCuration.cohort).toBe('fetus');

    const conformant = await apiRequest(request, token).get(`/phenopackets/${id}/export`);
    expect(await conformant.json()).not.toHaveProperty('hnf1bCuration');
  });

  test('invalid curation and laterality are rejected with 400', async ({ request }) => {
    const token = await signInAsCurator(request);

    const badEnum = await apiRequest(request, token).post('/phenopackets/', {
      data: {
        phenopacket: {
          id: `phenopacket-e2e-bad-${Date.now()}`,
          subject: { id: 'bad', sex: 'FEMALE' },
          metaData: { created: new Date().toISOString(), createdBy: 'e2e', resources: RESOURCES },
          hnf1bCuration: { detectionMethod: 'telepathy' },
        },
      },
    });
    expect(badEnum.status()).toBe(400);

    const badLaterality = await apiRequest(request, token).post('/phenopackets/', {
      data: {
        phenopacket: {
          id: `phenopacket-e2e-lat-${Date.now()}`,
          subject: { id: 'lat', sex: 'FEMALE' },
          metaData: { created: new Date().toISOString(), createdBy: 'e2e', resources: RESOURCES },
          phenotypicFeatures: [
            {
              type: { id: 'HP:0000122', label: 'Unilateral renal agenesis' },
              excluded: false,
              modifiers: [{ id: 'HP:0012832' }],
            },
          ],
        },
      },
    });
    expect(badLaterality.status()).toBe(400);
  });

  test('the create page loads with no console errors', async ({ page, request }) => {
    await signInAsCurator(request, page);
    const errors = [];
    page.on('console', (msg) => msg.type() === 'error' && errors.push(msg.text()));

    await page.goto('/phenopackets/create');
    await expect(page.getByRole('heading', { name: 'Create New Phenopacket' })).toBeVisible();

    expect(errors).toEqual([]);
  });

  test('a corpus-shaped age renders instead of N/A', async ({ page, request }) => {
    // Regression for spec §2.4: both readers queried a path that 0 of 923
    // records use, so last-encounter age never displayed.
    const token = await signInAsCurator(request);
    const id = await createRecord(request, token, {
      subject: { id: 'age-fixture', sex: 'FEMALE', timeAtLastEncounter: { iso8601duration: 'P9Y4M' } },
    });

    await signInAsCurator(request, page);
    await page.goto(`/phenopackets/${id}`);

    // Target the age field specifically — other fields legitimately show N/A.
    // Open the page once and read the DOM to find the stable selector, then
    // replace this locator with it.
    await expect(page.getByTestId('subject-age')).toContainText('9');
  });
});
```

- [ ] **Step 4: Pin down the age locator**

`getByTestId('subject-age')` is a placeholder. Open the detail page for a record with
a flat age, inspect the DOM around the rendered age, and either use an existing stable
selector or add `data-testid="subject-age"` to `SubjectCard.vue`. Do not ship a
`getByText('N/A')`-style assertion — other fields legitimately show N/A and it would
pass for the wrong reason.

- [ ] **Step 5: Run the checks**

Run: `cd frontend && npx playwright test tests/e2e/curation-contract.spec.js`
Expected: PASS. Playwright starts its own dev server on 5173; do not also run
`make frontend`, or `--strictPort` fails.

- [ ] **Step 6: Run every gate one final time**

```bash
cd backend && uv run ruff format && uv run ruff check . && uv run pytest -q
cd ../frontend && npx vitest run && npm run lint:check && npx prettier --check src tests && npm run build
cd ../mcp && uv run pytest -q
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add frontend/tests/e2e/curation-contract.spec.js
git commit -m "test(curation): end-to-end verification of the storage contract

Covers vocabulary reachability and shape, the HP:0000122 laterality asymmetry,
a clean create page, and the §2.4 age-display regression.

Refs: docs/superpowers/specs/2026-07-30-curation-data-model-design.md"
```

---

## Done criteria

Phases 1 and 2 are complete when:

- The create form emits no `publications` key, no `variation`, no `impact`/`caddScore` on `VariantInterpretation`, and a valid `moleculeContext`.
- `cycleState` does not mutate its prop.
- Age at last encounter renders on the phenopacket detail page for a record such as `phenopacket-219`; `age_utils.py` is gone.
- `hnf1bCuration` round-trips through create and update, with a typo inside the block rejected at 400.
- Segregation and laterality are validated against reference data on the REST write path, with HP:0000122 accepting Unilateral/Left/Right and rejecting only Bilateral.
- Four vocabulary endpoints and the laterality-policy endpoint return correctly-shaped data, and the composable exposes them.
- Export offers `conformant` and `full`, differing only by `hnf1bCuration`.
- The MCP contract regenerates cleanly and the no-silent-gaps test passes.
- **No existing phenopacket content has been rewritten.** A timestamp check cannot
  prove this — it misses revision mutations, cannot distinguish test fixtures from
  real records, and has no baseline. Take a content hash **before** starting Task 1
  and compare after Task 13:

```bash
# BEFORE any task runs — save this output.
psql -h localhost -p 5433 -U hnf1b_user -d hnf1b_phenopackets -tAc "
SELECT md5(string_agg(phenopacket_id || ':' || md5(phenopacket::text), ',' ORDER BY phenopacket_id))
FROM phenopackets;
SELECT md5(string_agg(id::text || ':' || md5(content_jsonb::text), ',' ORDER BY id))
FROM phenopacket_revisions;"
```

Re-run afterwards, excluding anything the tests created:

```bash
psql -h localhost -p 5433 -U hnf1b_user -d hnf1b_phenopackets -tAc "
SELECT md5(string_agg(phenopacket_id || ':' || md5(phenopacket::text), ',' ORDER BY phenopacket_id))
FROM phenopackets WHERE phenopacket_id NOT LIKE 'phenopacket-e2e-%'
                    AND phenopacket_id NOT LIKE 'phenopacket-export-test%';"
```

Both hashes must be **identical** to the baseline. Any difference means a task
rewrote stored content, which ADR 0003 defers to the conformance program.

- **Reference-data changes are expected and are the only permitted writes.** Confirm
  they are exactly what was intended — four new tables and six policy rows:

```bash
psql -h localhost -p 5433 -U hnf1b_user -d hnf1b_phenopackets -tAc "
SELECT count(*) FROM hpo_terms_lookup WHERE cardinality(allowed_modifiers) > 0;"
```

Expected: `6`. A larger number means the Task 7 UPDATE matched more rows than the
policy table lists.

- **Re-confirm no legacy record is now unsaveable.** Every laterality modifier in the
  corpus must sit on a term the policy admits:

```bash
psql -h localhost -p 5433 -U hnf1b_user -d hnf1b_phenopackets -tAc "
SELECT f->'type'->>'id', count(*)
FROM phenopackets p,
     jsonb_array_elements(p.phenopacket->'phenotypicFeatures') f,
     jsonb_array_elements(f->'modifiers') m
WHERE NOT EXISTS (
  SELECT 1 FROM hpo_terms_lookup h
  WHERE h.hpo_id = f->'type'->>'id' AND m->>'id' = ANY(h.allowed_modifiers))
GROUP BY 1;"
```

Expected: **no rows**. Any row is a record a curator can no longer save — add that
term to the policy rather than backfilling data.

Phase 3 — the curation console — is a separate spec and plan, written against this contract.
