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

/**
 * `VariantType` (curation console design spec §3.2) -> Sequence Ontology
 * term, for the `variationDescriptor.structuralType` select.
 *
 * No backend vocabulary endpoint exists for this field (it is not one of
 * the six curation vocabularies), so unlike every other select in the
 * curation console, this is a local constant rather than something fetched
 * via `usePhenopacketVocabularies`. Values verified against the real source
 * (`HNF1B_DataCuration.xlsx`, `Individuals` sheet, 939 rows,
 * sha256 0fcc5362148085ea0c55b682836c8f4ecef2b5be7f88a9038409f94d8a5061ec):
 * `df['VariantType'].value_counts()` = Deletion 431, SNV 341, indel 131,
 * Duplication 36 -- exactly these four, nothing else.
 *
 * ids/labels match the historical migration mapping
 * (`backend/migration/phenopackets/extractors.py::_add_molecular_consequence`)
 * so a curator's selection lines up with what the 908 already-migrated
 * records store on `molecularConsequences` for the same variant types. Note
 * SO:1000032's current formal SO name is "delins" (renamed from "indel" in
 * 2019, see `backend/app/ontology/data/ontology_snapshot.json`) -- the label
 * here stays "indel" to match both the sheet's own column value and the
 * label already stored on legacy records, rather than surprise curators with
 * an unfamiliar synonym.
 */
export const VARIANT_TYPES = [
  { id: 'SO:0000159', label: 'deletion' },
  { id: 'SO:1000035', label: 'duplication' },
  { id: 'SO:0001483', label: 'SNV' },
  { id: 'SO:1000032', label: 'indel' },
];

/**
 * The two members that belong on `variationDescriptor.structuralType`.
 *
 * The corpus partitions these four terms across two different fields, and the
 * split is exact: 404 deletion + 36 duplication on `structuralType`, 302 SNV +
 * 122 indel on `molecularConsequences`, 440 + 424 = 864 records, no overlap.
 *
 * The distinction is load-bearing, not cosmetic. The backend rejects any
 * descriptor that carries `structuralType` without an accompanying ISCN or
 * GA4GH-CNV expression ("Structural variant missing valid CNV notation",
 * backend/app/phenopackets/validation/variant_validator/validator.py:200), and
 * an SNV has neither. Writing all four to `structuralType` therefore made
 * every SNV and indel entered through the console unsaveable.
 */
export const STRUCTURAL_TYPE_IDS = new Set(['SO:0000159', 'SO:1000035']);

/** Every id in VARIANT_TYPES, so the variant-type member of
 * `molecularConsequences` can be replaced without disturbing a VEP-derived
 * consequence term (e.g. SO:0001583 missense_variant) sharing that array. */
export const VARIANT_TYPE_IDS = new Set(VARIANT_TYPES.map((t) => t.id));

/** @param {{id?: string} | null | undefined} term */
export const isStructuralType = (term) => !!term && STRUCTURAL_TYPE_IDS.has(term.id);
