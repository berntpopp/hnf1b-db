/**
 * PDB 2H8R Structure Constants
 *
 * The PDB 2H8R structure maps to UniProt P35680 residues 90-308.
 * Contains protein chains A, B (C, D in mmCIF) and DNA chains E, F (A, B in mmCIF).
 * mmCIF auth_seq_id matches UniProt numbering directly (no offset needed).
 */

/** First residue visible in PDB 2H8R structure */
export const STRUCTURE_START = 90;

/** Last residue visible in PDB 2H8R structure */
export const STRUCTURE_END = 308;

/** Gap start - linker region not resolved in crystal */
export const STRUCTURE_GAP_START = 187;

/** Gap end */
export const STRUCTURE_GAP_END = 230;

/**
 * HNF1B Domain Boundaries (UniProt P35680)
 *
 * Domain positions for the HNF1B transcription factor protein.
 */
export const DOMAIN_BOUNDARIES = {
  dimerization: { start: 1, end: 31 },
  pou_specific: { start: 88, end: 173 },
  pou_homeodomain: { start: 232, end: 305 },
  transactivation: { start: 314, end: 557 },
};

/**
 * HNF1B Gene Coordinates (GRCh38)
 *
 * Genomic coordinates for the HNF1B gene on chromosome 17.
 * Used for variant positioning and CNV detection.
 */
export const HNF1B_GENE = {
  chromosome: '17',
  start: 37686430,
  end: 37745059,
};
