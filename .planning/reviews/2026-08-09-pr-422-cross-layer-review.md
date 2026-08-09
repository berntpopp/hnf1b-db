# PR #422 Cross-Layer Review

**Date:** 2026-08-09

**Branch reviewed:** `fix/ontology-defects-and-curation-specs` at `1539b196107e960004dd382a2ee9ea0625c899d3`

**Decision:** **Do not merge as a completed data-quality or lossless-curation fix.**

**Required architecture:** one individual -> one canonical Phenopacket; every source publication/report row -> one typed observation inside that Phenopacket.

## Executive finding

PR #422 improves ontology validation, revision-aware editing, laterality support, and the curation UI. Its recorded CI checks are green. It nevertheless does not satisfy the claimed source-fidelity outcome.

The live authoritative `Individuals` sheet contains 939 rows and 60 columns for 864 distinct individuals. Seventy-three individuals have two or three report rows. The current importer groups by `individual_id` and then resolves row differences with first-row, first-non-unknown, maximum-age, present-wins, and HPO-ID-deduplication rules. The form edits the flattened result. This preserves individual cardinality but discards observation cardinality and provenance.

The correct repair is not one Phenopacket per report. The database and its analytics consistently use a Phenopacket as an individual-level record. The repair is an observation ledger inside the revisioned `hnf1bCuration` block and a deterministic, backend-owned projection from those observations into the GA4GH-facing fields.

## Evidence baseline

| Measure                                                 | Verified value | Consequence                                                            |
| ------------------------------------------------------- | -------------: | ---------------------------------------------------------------------- |
| Live `Individuals` rows                                 |            939 | Import conservation must account for 939 observations.                 |
| Live columns                                            |             60 | Coverage must be asserted column by column.                            |
| Distinct `individual_id` values                         |            864 | Canonical database cardinality remains 864 source individuals.         |
| Repeated individuals                                    |             73 | Case-level flattening is intrinsically lossy.                          |
| Existing DB records / soft-deleted                      |       923 / 10 | Database-wide identity cannot be forced to source cardinality offline. |
| Existing DB records without source row                  |             59 | Preserve as `legacy_unbound` pending identity/provenance adjudication. |
| Phenotype columns                                       |             30 | Each imported observation needs 30 explicit phenotype assessments.     |
| Phenotype cells                                         |         28,170 | Conservation denominator for phenotype status.                         |
| Literal `not reported` phenotype cells                  |         20,171 | Absence cannot mean both uncurated and source-silent.                  |
| Literal `no` phenotype cells                            |          4,620 | Negative evidence must remain tied to its report.                      |
| Literal `yes` phenotype cells                           |          1,639 | Plain presence is distinct from categorical positive values.           |
| Positive categorical phenotype cells                    |          1,720 | Includes CKD stage, biopsy finding, and laterality.                    |
| Blank phenotype cells                                   |              1 | This is the actual uncurated state.                                    |
| Compound unilateral assertions                          |            408 | This is a source-row assertion count, not a canonical-feature count.   |
| Deduplicated features eligible for unambiguous backfill |            377 | Existing migration restores these canonical features.                  |
| Conflicting `(individual, phenotype)` keys              |             18 | Conflicts must remain visible; 10 currently lack canonical laterality. |
| Gestational-week source cells                           |             19 | Current parser converts examples such as `28w` to `P28Y`.              |
| `PrematureBirth=not applicable` rows                    |             19 | Current importer incorrectly projects these as present.                |

The live `Phenotypes` source still contains `HP:0033133` labelled “Renal cortical hyperechogenicity”; the intended concept is `HP:0033132`. The current source-integrity check correctly rejects this contradiction, which means the configured live import cannot complete until the source is corrected or a reviewed correction ledger is applied before ontology construction.

## Severity-ranked findings

### Critical

1. **The authoritative observation model is missing.** The importer collapses 939 report rows into 864 documents before preserving their meanings. Conflicts occur in publication type, sex, age, variant, detection method, segregation, family history, comments, reviewer/date, and phenotype columns. The current JSON cannot reconstruct the source observations.

   The source audit found 710 coarse five-state phenotype conflicts across individual/question pairs. The current “present wins” merge can attach evidence from an excluded report to the winning present feature, changing evidence polarity rather than merely deduplicating it.

2. **Source-silent and uncurated are conflated.** `not reported` phenotype cells are skipped, while the UI treats a missing feature as generic unknown. A curator cannot tell whether a paper was checked and silent or the field has never been reviewed.

3. **Compound laterality is destroyed on edit.** `unilateral left` and `unilateral right` require both `Unilateral` and a side modifier. The UI loads only `modifiers[0]` and saves one modifier, so a round-trip loses left/right.

4. **Gestational ages are clinically corrupted.** Week-form inputs fall through to the numeric-years parser. `28w` becomes 28 years, which is not a display defect but a false clinical assertion.

5. **The live importer is blocked by a source ontology contradiction.** Failing closed is correct; declaring the import fixed while its configured source still fails is not.

6. **Published-head and revision invariants are not real.** Public visibility has a fast path that returns the mutable working copy, and public filters/counts use working-copy generated fields. Revision rows described as immutable are updated during draft save and publication. A source correction cannot be audited reliably until revisions are append-only and every public reader resolves the real head.

7. **There is no centralized public PII boundary.** Anonymous detail can return reviewer metadata, the importer can persist a source email fallback, and frontend copy/download serializes the loaded document rather than calling the export sanitizer. Every public surface needs one recursive allowlist serializer.

8. **The current projection fabricates temporal and disease assertions.** `AgeReported` is copied into feature onset, prenatal is mapped to congenital, unknown numeric strings become years, and every subject receives congenital RCAD even though an HNF1B finding—especially a VUS/benign finding—does not itself establish that diagnosis.

9. **Several variant/evidence structures are not GA4GH v2 semantics.** Current paths conflate ACMG pathogenicity with clinical contribution, can invent a transcript/ISCN/dbVar-derived content, merge CNVs by overlap, use non-referential `subjectOrBiosampleId`, and store nonstandard extension/evidence fields. The official protobuf parser, not the permissive local schema, must be the export oracle.

### High

1. **The “408 restored” claim is materially imprecise.** There are 408 raw source-row laterality assertions, 377 unambiguous deduplicated features restored, 594 added modifier objects, and 18 conflict keys excluded. Eight conflict keys already had bilateral canonical data; ten remain unresolved. These four quantities must never be presented as interchangeable.

2. **Fresh imports use row order as an undeclared clinical resolver.** `_merge_phenotypes()` deduplicates by HPO ID without reconciling modifiers. Reversing report order can change the canonical result.

3. **Publication edits are lossy.** Existing external references may contain PMID, DOI, description/type, and per-feature evidence. The edit view reduces them to PMID strings and recreates ID-only references.

4. **Scientific source fields are absent or transformed without a raw counterpart.** The importer drops `Cohort`, `DetecionMethod`, `FamilyHistory`, true `Segregation`, classification system/date/comment, `Problematic`, `DupCheck`, `hg19`, and both `_INFO` fields. `Varsome`, CNV descriptions, and coordinates are transformed without preserving the verbatim source value.

5. **Provenance and evidence cannot be curated faithfully.** Phenotype evidence is attached to only the first PMID; `ReviewBy` and `ReviewDate` are hidden or overwritten; repeated observations can have different reviewers, dates, and publications.

6. **`not applicable` is treated as present.** This is especially unsafe for `PrematureBirth` and demonstrates that a three-state phenotype control is insufficient.

7. **Importer failures can produce a committed partial corpus.** Individual build errors and storage errors are logged and skipped; the orchestrator ignores `stored_count`; reimports reset the optimistic revision to 1; head revision creation is not a safe atomic corpus replacement.

8. **The laterality migration validates only its working-copy accounting.** It permits unmatched/disagreement rows and does not require the public head copy to match, so the public record can remain stale.

9. **A public reviewer sheet contains a populated credential-like column.** Values were not inspected. Public access is an intentional project requirement and remains enabled. Remove credential-bearing columns from the public schema, rotate any affected credentials, and make the importer reject forbidden secret columns. No password or source email should enter Phenopacket JSON.

10. **“Conformant” export is not a conformance guarantee.** It removes `hnf1bCuration` but does not prove the remaining document against the official Phenopackets parser. Rename the contract to an actual `ga4gh` representation only after parser validation.

### Medium

1. `report_id` and `IndividualIdentifier` are merged into an untyped `subject.alternateIds` set.
2. dbVar data is imported as an extension while the UI reads/writes `xrefs`.
3. Domain validation omits at least publication type and classification system; nested extensions and expressions remain weakly typed.
4. `HP:0003674` (“Onset”) is still used as if it meant postnatal onset and is treated as age one in survival logic.
5. The modifier sheet GID is configured but not loaded; the configured GID currently fails, so hardcoded terms are silently substituted.
6. A documented environment override for the source spreadsheet is not honored.

## Ontology correction accounting

The repository must replace the phrase “14 wrong identifiers” with a versioned correction ledger. Current prose is internally contradictory: the defect report enumerates 13 distinct wrong identifier values (T1-T13), while other planning prose claims 14. At least one separately counted change corrects a label without changing an identifier. The implementation must derive summary counts from the ledger rather than hardcode them in prose.

Each ledger row must contain:

- defect key;
- location/path;
- wrong identifier and label;
- intended identifier and canonical label;
- correction kind: `identifier`, `label_only`, `source_identifier`, or `mapping`;
- evidence source and ontology release;
- affected working-copy and head-revision counts;
- migration/import/test coverage.

The claim is accepted only when every ledger row has an executable test and the authoritative pinned-manifest preflight passes; live-source access is optional drift detection.

## Why current tests are insufficient

Focused backend and frontend suites pass, but several tests encode the lossy contract:

- the Playwright flow manually re-enters three hand-selected rows rather than exercising Sheets -> importer -> database -> API -> form -> save -> reload;
- it substitutes fake PMIDs, parsed Varsome/HGVS values, and invented ISCN;
- it explicitly omits `_INFO`, source reviewer email, prenatal/not-reported age semantics, and compound left/right laterality;
- it expects absent `not reported` features and source-reviewer disappearance;
- it never proves observation count, source-field count, evidence attribution, or public-head equality.

Green CI therefore demonstrates consistency with current behavior, not conservation of the authoritative data.

## Required target contract

```text
Google Sheets row (939)
        |
        v
typed report observation (939, lossless scientific source meaning)
        |
        +--> conflict/resolution engine
        |
        v
canonical GA4GH projection (864 individual Phenopackets)
        |
        +--> working JSONB + immutable revisions + audit
        +--> public head after explicit publish
        +--> analytics/search/MCP using individual-level projection
```

The source observations and explicit append-only corrections/resolutions are authoritative. Canonical `subject`, `phenotypicFeatures`, `interpretations`, `diseases`, `metaData.externalReferences`, and evidence are derived. Clients must not be able to save a canonical projection that disagrees with the observation ledger and resolution set. Internal storage should key observations by stable UUIDv5 IDs; the curator API can expose them as a sorted list.

## Dependency and security review

PR #422 does not directly change dependency manifests or workflows. Eight Dependabot alerts remain: five Undici alerts, backend and MCP `cryptography` alerts, and a DOMPurify alert.

- Do not merge the individual Tiptap PRs independently. Align `@tiptap/core`, `extension-link`, `extension-mention`, `starter-kit`, and `vue-3` to 3.29.2 and regenerate one lockfile. PR #430 currently fails with an exact-peer conflict; PR #428 produces a split nested dependency graph.
- Do not apply PR #431 as-is. Its requirements pins are not backed by `backend/uv.lock`, and its advertised `pydantic==2.13.4` / `pydantic-core==2.47.0` pair is incompatible. Update `pyproject.toml`, run `uv lock`, then regenerate exported requirements from that lock.
- Update backend and MCP cryptography locks to 50.x; backend is not covered by the current MCP-only PR.
- Consolidate frontend manifest changes and regenerate `package-lock.json` once, including Undici 7.29.0 and DOMPurify 3.4.13.
- Integrate workflow action upgrades together and correct stale version comments. Node 24 actions require modern runners; the observed hosted runner is compatible, but self-hosted reuse needs an explicit minimum-runner check.

## Merge gates

PR #422, or a replacement branch, is ready only when all gates pass:

1. Exactly 939 observations are imported into exactly 864 source-backed Phenopackets from the pinned fixture; the 59 currently known DB-only records remain explicitly `legacy_unbound` pending provenance review.
2. Every observation preserves all 60 source dimensions, subject only to the documented credential/PII redaction policy.
3. All 28,170 phenotype cells are accounted for by an explicit status; `not_reported`, `not_applicable`, excluded, and present remain distinct.
4. All 408 compound unilateral source assertions survive in observations; canonical accounting reports 377 unambiguous restorations and 18 surfaced conflict keys, not “408 features restored.”
5. Import output is invariant under report-row permutation.
6. Gestational weeks never enter ISO 8601 years; invalid or ambiguous ages fail closed.
7. Reimport is idempotent, transactionally all-or-nothing, revision-monotonic, and cannot overwrite an active curator draft.
8. Working copy and public head are both validated after migration; no unmatched fixture rows or disagreements are tolerated without an explicit reviewed resolution.
9. An end-to-end fixture runs importer -> database -> API -> editor -> save -> reload and proves observation/provenance/field conservation.
10. The ontology correction ledger, authoritative pinned-manifest preflight, dependency locks, alert scan, and required CI checks are green. A live-sheet comparison may detect drift but is never migration input.
11. Older revision bytes never change, and public detail/list/filter/search/materialized views/export/MCP all resolve the same head revision.
12. Recursive privacy tests prove no restricted reviewer/source identifiers or email patterns leave curator-only representations.

## Recommendation

Treat the current PR as a valuable prototype and evidence bundle, not the final remediation. Implement the source-observation contract first, migrate/import into it, make the backend the only canonical projection authority, then rebuild the form around observations and conflicts. Integrate dependency/security work in an isolated parallel lane and merge it before or independently of the clinical-data migration, after both lanes pass their own gates.
