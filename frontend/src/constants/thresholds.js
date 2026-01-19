/**
 * Distance Thresholds for DNA Proximity Analysis
 *
 * These thresholds categorize variant-to-DNA distances in the PDB 2H8R structure.
 * Based on structural biology conventions for protein-DNA interactions.
 */

/**
 * Close distance threshold (Angstroms).
 * Residues closer than this value likely have direct DNA contact.
 */
export const DISTANCE_CLOSE_THRESHOLD = 5;

/**
 * Medium distance threshold (Angstroms).
 * Residues between CLOSE and MEDIUM may have indirect effects on DNA binding.
 */
export const DISTANCE_MEDIUM_THRESHOLD = 10;

/**
 * Size threshold for structural variants (base pairs).
 * Variants >= this size are classified as CNVs rather than indels.
 */
export const STRUCTURAL_VARIANT_SIZE_THRESHOLD = 50;

/**
 * Overlap threshold for variant label positioning (amino acids).
 * Labels closer than this are stacked to avoid visual collision.
 */
export const LABEL_OVERLAP_THRESHOLD = 30;
