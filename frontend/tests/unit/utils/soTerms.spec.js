/**
 * Unit tests for the VEP-consequence -> Sequence Ontology accession map.
 *
 * `SO_TERMS` is written straight into
 * `variationDescriptor.molecularConsequences[]` (see VariantAnnotationForm.vue),
 * which `backend/app/ontology/conformance.py`'s `ONTOLOGY_PATHS` now covers
 * (2026-07-30 fix) so a wrong id/label pair here would fail the backend's A3
 * conformance sweep. All 29 entries were additionally verified live against
 * OLS4 (`/ols4/api/ontologies/so/terms?iri=...`, never `/search`) on
 * 2026-07-30 -- every VEP consequence key matches its SO id's live canonical
 * `label` exactly. `backend/tests/test_so_terms_conformance.py` re-checks
 * every pair against the pinned ontology snapshot and parses this file
 * directly to catch drift between the two.
 *
 * This spec is the frontend-side regression fence: it pins the exact,
 * live-verified map so an accidental future edit (e.g. a copy-paste id
 * swap when a new consequence is added) fails a fast, offline test instead
 * of shipping silently -- the frontend test suite previously only exercised
 * `missense_variant` via VariantAnnotationForm.spec.js.
 */
import { describe, it, expect } from 'vitest';
import { SO_TERMS, soIdFor } from '@/utils/soTerms';

// Live-verified 2026-07-30 against OLS4 `/ols4/api/ontologies/so/terms?iri=...`
// (exact identifier lookup, never `/search`): every key here is the SO id's
// canonical `label` field verbatim. Keep in lockstep with SO_TERMS itself --
// `backend/tests/test_so_terms_conformance.py` mirrors this same map and
// checks it against the pinned snapshot.
const LIVE_VERIFIED_SO_TERMS = {
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

describe('SO_TERMS', () => {
  it('matches the live-verified id map exactly (29 entries, no drift)', () => {
    expect(SO_TERMS).toEqual(LIVE_VERIFIED_SO_TERMS);
  });

  it('has exactly 29 entries', () => {
    expect(Object.keys(SO_TERMS)).toHaveLength(29);
  });

  it('every accession is a well-formed SO id', () => {
    for (const [consequence, soId] of Object.entries(SO_TERMS)) {
      expect(soId, `${consequence} -> ${soId}`).toMatch(/^SO:\d{7}$/);
    }
  });

  it('every accession is unique (no two consequences share one SO id)', () => {
    const ids = Object.values(SO_TERMS);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('soIdFor resolves every mapped consequence and undefined otherwise', () => {
    for (const [consequence, soId] of Object.entries(SO_TERMS)) {
      expect(soIdFor(consequence)).toBe(soId);
    }
    expect(soIdFor('not_a_real_consequence')).toBeUndefined();
  });
});
