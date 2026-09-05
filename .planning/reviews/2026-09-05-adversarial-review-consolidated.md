# Independent Phenopacket Review — Consolidated Adversarial Review

**Date:** 2026-09-05  
**Base Tree:** `f6429ec` (`main` following dependency consolidation and release bumps)  
**Branch:** `feat/peer-review-workflow`  
**Method:** Deep adversarial review across three expert lenses:
1. Backend Security, Concurrency & Invariants
2. Clinical Curation & Data Science Completeness (GA4GH Phenopackets v2 & ACMG standards)
3. Frontend Architecture & Impeccable UI/UX Design

---

## Executive Summary

The underlying architecture of PR #453 provides exceptional core guarantees:
- Strict four-eyes review policy preventing self-approval by owners, submitters, and active-cycle contributors;
- Row-lock serialization and database triggers closing approval vs. blocking-issue races;
- Immutable v2 ledger hashes and canonical full-content SHA-256 digests;
- Server-driven review queue and coherent review context DTOs.

However, deep inspection revealed 4 high-impact opportunities for clinical data curation and user experience excellence:

1. **[Clinical Data Science] Genomic Interpretation Identity Masking**: `_identity` in `ReviewService` did not recognize `genomicInterpretations` containing nested `variationDescriptor.id`, causing array diffs of variants to fall back to fragile index-based comparison.
2. **[Clinical Data Science] Curation Profile Missing from Candidate Snapshot**: `CandidateSnapshot.vue` omitted `hnf1bCuration` from `DISPLAYED_FIELDS`, causing all HNF1B-specific clinical curation (cohort, detection method, family history, publication type, classification system, and case comments) to be dumped as raw JSON rather than structured cards.
3. **[UI/UX & Impeccable] Semantic Diff Visual Ergonomics**: `SemanticDiff.vue` rendered all diff operations (`added`, `removed`, `changed`) in identical neutral grey boxes without visual distinction, and lacked section grouping.
4. **[UI/UX & Ergonomics] Review Queue Action & Eligibility Polish**: In `ReviewQueue.vue`, action buttons indiscriminately displayed "Review" regardless of state or eligibility (including own drafts), and eligibility was presented as unstyled text rather than clear status chips.

---

## Findings & Remediation Plan

| ID | Domain | Severity | Description | Remediation |
|---|---|---|---|---|
| **DS-1** | Data Science | **High** | `CandidateSnapshot.vue` ignores `hnf1bCuration`, dumping core curation metadata to raw JSON. | Add a structured `CurationProfileCard` component and register `hnf1bCuration` in `DISPLAYED_FIELDS`. |
| **DS-2** | Data Science | **High** | `_identity` in `ReviewService` fails on `genomicInterpretations` (`variantInterpretation.variationDescriptor.id`), falling back to index diffing. | Extend `_identity` to inspect `variationDescriptor.id` directly and within `variantInterpretation`. Add regression tests. |
| **UI-1** | Impeccable UX | **High** | `SemanticDiff.vue` has no distinct visual cues for added/removed/changed operations. | Implement accessible, restrained semantic styling with subtle color tints, accent indicators, and icons matching Impeccable standards. |
| **UI-2** | Impeccable UX | **High** | Semantic changes are displayed in a single flat list without section grouping. | Group changes by clinical section (`Subject`, `Phenotypes`, `Diseases`, `Variants/Interpretations`, `Measurements`, `Metadata`) with counts and badges. |
| **UI-3** | Impeccable UX | **Medium** | Review Queue action buttons and eligibility labels lack contextual state awareness. | Contextualize action labels ("Review" vs "Open" vs "Edit") and style eligibility and open issue counts as scannable chips. |

---

## Verification Strategy

1. Implement backend `_identity` enhancement with unit test in `test_review_context.py`.
2. Implement frontend `CurationProfileCard.vue` and integrate into `CandidateSnapshot.vue`.
3. Enhance `SemanticDiff.vue` with section grouping, operation styling, and clear clinical formatting.
4. Polish `ReviewQueue.vue` with contextual actions and status chips.
5. Verify with Vitest and Playwright test suites.
6. Conduct runtime monkey testing against running dev stack.
