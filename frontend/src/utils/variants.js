/**
 * Variant type detection and classification utilities.
 *
 * Provides functions to determine variant types from HGVS notation and genomic coordinates.
 * Handles SNVs, indels, CNVs, and other structural variants.
 *
 * @module utils/variants
 */

import { extractCNotation } from './hgvs';

// HNF1B gene boundaries on chromosome 17 (GRCh38)
const HNF1B_START = 36098063;
const HNF1B_END = 36112306;

/**
 * Determine the variant type from HGVS notation and genomic coordinates.
 *
 * Detection priority:
 * 1. Large CNVs (from genomic coordinates)
 * 2. Complex indels (delins pattern)
 * 3. Simple deletions, duplications, insertions
 * 4. SNVs (single nucleotide variants)
 * 5. Fallback to stored variant_type
 *
 * @param {Object} variant - Variant object with transcript, hg38, and variant_type fields
 * @returns {string} Variant type classification
 *
 * @example
 * getVariantType({ hg38: '17:36098063-36112306:...' }) // Returns: 'CNV'
 * getVariantType({ transcript: 'NM_000458.4:c.544delinsAG' }) // Returns: 'indel'
 * getVariantType({ transcript: 'NM_000458.4:c.544del' }) // Returns: 'deletion'
 * getVariantType({ transcript: 'NM_000458.4:c.544G>T' }) // Returns: 'SNV'
 */
export function getVariantType(variant) {
  if (!variant) return 'Unknown';

  // Check if this is a large CNV (has genomic coordinates in format chr:start-end)
  // CNVs are typically whole gene or multi-gene deletions/duplications
  if (variant.hg38) {
    const cnvMatch = variant.hg38.match(/(\d+|X|Y|MT?):(\d+)-(\d+):/);
    if (cnvMatch) {
      return 'CNV';
    }
  }

  // For small variants, detect type from c. notation
  const cNotation = extractCNotation(variant.transcript);

  if (cNotation && cNotation !== '-') {
    // Check for delins (complex indels) FIRST before checking for simple del/ins
    // Match patterns like "delins", "delGCTCTGins", "delAins" etc.
    if (/del[A-Z]*ins/.test(cNotation)) {
      return 'indel';
    }

    // Check for deletions (but not duplications)
    if (/del/.test(cNotation) && !/dup/.test(cNotation)) {
      return 'deletion';
    }

    // Check for duplications
    if (/dup/.test(cNotation)) {
      return 'duplication';
    }

    // Check for insertions
    if (/ins/.test(cNotation)) {
      return 'insertion';
    }

    // Check for substitutions (true SNVs: single position with >)
    if (/>\w$/.test(cNotation) && !/[+-]/.test(cNotation) && !/_/.test(cNotation)) {
      return 'SNV';
    }
  }

  // Fall back to stored variant_type
  return variant.variant_type || 'Unknown';
}

/**
 * Check if a variant is a Copy Number Variant (CNV).
 * CNVs are large structural variants that extend beyond HNF1B gene boundaries.
 *
 * @param {Object} variant - Variant object with hg38 field
 * @returns {boolean} True if variant is a CNV (>= 50bp and extends beyond HNF1B)
 *
 * @example
 * isCNV({ hg38: '17:36000000-36200000:...' }) // Returns: true (large, extends beyond HNF1B)
 * isCNV({ hg38: '17:36098100-36098150:...' }) // Returns: false (small, within HNF1B)
 * isCNV({ transcript: 'NM_000458.4:c.544del' }) // Returns: false (no genomic coords)
 */
export function isCNV(variant) {
  if (!variant?.hg38) return false;

  // Parse genomic coordinates: chr:start-end:...
  const match = variant.hg38.match(/(\d+|X|Y|MT?):(\d+)-(\d+):/);
  if (!match) return false;

  const start = parseInt(match[2]);
  const end = parseInt(match[3]);
  const size = end - start;

  // CNV criteria:
  // 1. Size >= 50bp (structural variant threshold)
  // 2. Extends beyond HNF1B gene boundaries
  const extendsBeyondHNF1B = start < HNF1B_START || end > HNF1B_END;
  return size >= 50 && extendsBeyondHNF1B;
}

/**
 * Check if a variant is an indel (insertion-deletion).
 * Complex variants with both deletion and insertion components.
 *
 * @param {Object} variant - Variant object with transcript field
 * @returns {boolean} True if variant is an indel
 *
 * @example
 * isIndel({ transcript: 'NM_000458.4:c.544delinsAG' }) // Returns: true
 * isIndel({ transcript: 'NM_000458.4:c.544del' }) // Returns: false
 */
export function isIndel(variant) {
  const cNotation = extractCNotation(variant?.transcript);
  if (!cNotation || cNotation === '-') return false;

  return /del[A-Z]*ins/.test(cNotation);
}

/**
 * Check if a variant affects a splice site.
 * Detects splice donor (+1, +2) and acceptor (-1, -2) positions.
 *
 * @param {Object} variant - Variant object with transcript field
 * @returns {boolean} True if variant is a splice site variant
 *
 * @example
 * isSpliceVariant({ transcript: 'NM_000458.4:c.544+1G>T' }) // Returns: true (donor)
 * isSpliceVariant({ transcript: 'NM_000458.4:c.544-2A>G' }) // Returns: true (acceptor)
 * isSpliceVariant({ transcript: 'NM_000458.4:c.544G>T' }) // Returns: false
 */
export function isSpliceVariant(variant) {
  const cNotation = extractCNotation(variant?.transcript);
  if (!cNotation || cNotation === '-') return false;

  // Match splice donor (+1, +2) or acceptor (-1, -2) positions
  return /[+-][12]/.test(cNotation);
}

/**
 * Get variant size in base pairs from HGVS notation or genomic coordinates.
 *
 * @param {Object} variant - Variant object with transcript and/or hg38 fields
 * @returns {number|null} Variant size in bp, or null if not determinable
 *
 * @example
 * getVariantSize({ hg38: '17:36098063-36112306:...' }) // Returns: 14243
 * getVariantSize({ transcript: 'NM_000458.4:c.544_547del' }) // Returns: 4
 * getVariantSize({ transcript: 'NM_000458.4:c.544G>T' }) // Returns: 1
 */
export function getVariantSize(variant) {
  if (!variant) return null;

  // Try genomic coordinates first (most accurate)
  if (variant.hg38) {
    const match = variant.hg38.match(/(\d+|X|Y|MT?):(\d+)-(\d+):/);
    if (match) {
      const start = parseInt(match[2]);
      const end = parseInt(match[3]);
      return end - start;
    }
  }

  // Try to determine from c. notation
  const cNotation = extractCNotation(variant.transcript);
  if (!cNotation || cNotation === '-') return null;

  // Range deletion/duplication: c.544_547del
  const rangeMatch = cNotation.match(/(\d+)_(\d+)/);
  if (rangeMatch) {
    const start = parseInt(rangeMatch[1]);
    const end = parseInt(rangeMatch[2]);
    return end - start + 1;
  }

  // Single position change: c.544G>T
  if (/^\d+[A-Z]>[A-Z]$/.test(cNotation) || /^c\.\d+[A-Z]>[A-Z]$/.test(cNotation)) {
    return 1;
  }

  return null;
}
