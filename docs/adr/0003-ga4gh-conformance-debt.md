# ADR 0003: Accept and defer the GA4GH Phenopackets v2 conformance debt

**Status:** Accepted
**Date:** 2026-07-30
**Context:** Adversarial review of the curation data model design
([spec](../superpowers/specs/2026-07-30-curation-data-model-design.md)) surfaced five
pre-existing nonconformances in the migrated corpus.

## Context

The 923-record corpus was produced by a one-off migration from
`HNF1B_DataCuration.xlsx`. Three rounds of adversarial review established that five of
its structural choices do not conform to GA4GH Phenopackets v2, as defined by the
pinned `phenopackets 2.0.2.post5` package.

None of these were known before this review. All predate the curation console work and
none were introduced by it.

### D1 — ACMG classifications stored in `interpretationStatus`

`GenomicInterpretation.InterpretationStatus` admits exactly
`UNKNOWN_STATUS, REJECTED, CANDIDATE, CONTRIBUTORY, CAUSATIVE`. The corpus stores
`PATHOGENIC`, `LIKELY_PATHOGENIC`, `UNCERTAIN_SIGNIFICANCE` and `LIKELY_BENIGN` there.
The correct field, `VariantInterpretation.acmgPathogenicityClassification`, exists and
admits exactly those values.

- **Extent:** 864 records. Written by `backend/migration/phenopackets/extractors.py:547`.
- **Blessed by:** `backend/app/phenopackets/validation/schema_validator.py:184-193`.
- **Read by:** `sql_fragments/paths.py:22` (`INTERP_STATUS_PATH`, used for P/LP
  filtering), the aggregation and comparison queries, `InterpretationsCard.vue:261`,
  and MCP `individuals.py:160`.

### D2 — `variantInterpretation.extensions` is not a GA4GH field

`VariantInterpretation` has exactly three fields:
`acmg_pathogenicity_classification`, `therapeutic_actionability`,
`variation_descriptor`. The corpus stores `classification_criteria` on a nonexistent
`extensions` member.

- **Extent:** 864 records. Written by `extractors.py:573`.
- The only sanctioned extension slot is `VariationDescriptor.extensions`.

### D3 — `Extension.value` must be a string

`org.ga4gh.vrsatile.v1.Extension.value` is protobuf type 9 (string). Verified:

```python
ParseDict({"extensions":[{"name":"coordinates","value":{"assembly":"GRCh38"}}]},
          VariationDescriptor())
# → Failed to parse value field: expected string or bytes-like object, got 'dict'
```

Every extension in the corpus carries an object: `coordinates` (440),
`external_reference` (440), `classification_criteria` (864), `copy_number` (13),
`zygosity` (13). `vep_annotation` — written by
`scripts/enrich_phenopackets_with_vep.py:167`, asserted by
`tests/test_classification_validation.py`, present in 0 records today — is the same
shape.

### D4 — `timeAtLastEncounter` omits the `age` wrapper

`TimeElement` is a `oneof` over
`gestationalAge | age | ageRange | ontologyClass | timestamp | interval`, and `Age`
wraps `iso8601duration`. The corpus stores `{"iso8601duration": …}` directly.

- **Extent:** 664 records. 0 records use the conformant path.
- **Live consequence:** `SubjectCard.vue:119` and `PagePhenopacket.vue:450` read the
  conformant path and therefore render nothing. Fixed in Phase 1 by correcting the
  readers, not the data.

### D5 — Laterality flattened to Bilateral

The source `Phenotype_modifier` sheet defines HP:0012832 Bilateral, HP:0012833
Unilateral, HP:0012835 Left and HP:0012834 Right. The corpus uses only Bilateral (771
uses). Roughly 400 unilateral/left/right annotations across five phenotypes are
indistinguishable from "laterality not stated".

## Decision

**Accept the debt. Do not pay it as part of the curation console program.**

New curated facts follow the corpus's existing conventions, including its
nonconformances, so that the eventual migration is a single uniform pass rather than a
reconciliation of two competing representations. Concretely, the `segregation`
extension introduced by the curation spec is object-valued (D3), and ACMG and
`classification_criteria` are left where they are (D1, D2).

Two debts get partial relief because it costs nothing:

- **D4** — the two frontend readers are corrected to the corpus path in Phase 1, so
  age renders. The 664 records are not migrated.
- **D5** — laterality *modelling* and validation land with the curation spec, so new
  records are annotated correctly. The ~400 legacy annotations are not restored.

## Consequences

**Accepted:**

- The corpus cannot be validated against an official GA4GH schema, and
  `google.protobuf.json_format.ParseDict` rejects its extensions. Any claim of
  Phenopackets v2 conformance in documentation or publication must be qualified.
- The export endpoint's `conformant` mode strips HNF1B-specific curation but does
  **not** produce a GA4GH-valid document. This is stated explicitly in the spec.
- P/LP filtering continues to read `interpretationStatus`. The curation console
  therefore does not write that field, so filter behaviour is unchanged for new records
  (spec §8.1).
- The debt grows by exactly one item (the `segregation` extension), deliberately.

**Deferred to a conformance program**, which requires its own spec and risk budget:

- Migrating D1–D5 across 864–923 records, revision-aware: both
  `phenopackets.phenopacket` and `phenopacket_revisions.content_jsonb` at
  `head_published_revision_id`, with per-record preimages and hashes rather than a
  name-based downgrade.
- Updating every reader in lock-step: aggregations, comparison and survival SQL, global
  search and its materialized views, `InterpretationsCard.vue`, MCP shaping and its
  regenerated contract.
- Refreshing the aggregation materialized views and `global_search_index`, and
  accounting for the five-minute HTTP/client caching on the all-variants endpoint.
- Choosing a conformant representation for extension values (canonical serialized
  strings with a documented schema, or promotion to typed GA4GH/VRS fields where they
  exist).
- Reconciling source cardinality first: 939 spreadsheet rows over 864 distinct
  `individual_id`, 148 rows flagged duplicate, and 59 DB records with no source row.
  Merge rules for disagreeing duplicate rows are undefined and must precede any
  backfill.
- Handling the 90 records whose detection method is stranded in free text inside
  `metaData.comment`.
- Deciding whether raw source data can be committed at all: `ReviewBy` contains
  institutional email addresses that the database does not currently hold
  (`metaData.reviewer` stores display names), and the dataset license is unspecified in
  `docs/references/data-sources.md:318`.

## Alternatives considered

**Pay the debt first.** Correct, and it front-loads the highest-risk work in the
program: 923 records across two authoritative copies, every aggregation, search, the
materialized views and the MCP contract — before curators get any improvement to a form
that currently captures six of 28 curation dimensions. Rejected on sequencing, not on
merit.

**Two parallel tracks.** Curation console and conformance migration proceeding
independently against a written interface contract. Rejected because both tracks modify
the same validator, services, aggregation SQL and MCP contract, so they would serialize
at review time anyway while doubling the in-flight risk.

**Make only the new fields conformant.** A string-valued `segregation` extension
alongside five object-valued ones. Rejected: it gives the console two serialization
rules for no present benefit and leaves the migration with a heterogeneous corpus to
reconcile instead of a uniform one.
