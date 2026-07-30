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
