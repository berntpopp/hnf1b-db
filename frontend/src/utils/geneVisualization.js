/**
 * Gene Visualization Utilities
 *
 * Shared utilities for HNF1B gene and 17q12 region visualizations.
 * Extracted from HNF1BGeneVisualization.vue for reuse and maintainability.
 *
 * @module utils/geneVisualization
 */

/**
 * HNF1B exon coordinates (GRCh38, NM_000458.4)
 * Note: Gene is on minus strand, so exon 1 is at higher genomic coordinates
 */
export const HNF1B_EXONS = [
  { number: 1, start: 37744540, end: 37745059, size: 519, domain: "5' UTR" },
  { number: 2, start: 37739439, end: 37739639, size: 200, domain: null },
  { number: 3, start: 37733556, end: 37733821, size: 265, domain: 'POU-S' },
  { number: 4, start: 37731594, end: 37731830, size: 236, domain: 'POU-H' },
  { number: 5, start: 37710502, end: 37710663, size: 161, domain: 'POU-H' },
  { number: 6, start: 37704916, end: 37705049, size: 133, domain: null },
  { number: 7, start: 37700982, end: 37701177, size: 195, domain: 'Transactivation' },
  { number: 8, start: 37699075, end: 37699194, size: 119, domain: 'Transactivation' },
  { number: 9, start: 37686430, end: 37687392, size: 962, domain: "3' UTR" },
];

/**
 * Default chr17q12 region data (fallback if API unavailable)
 */
export const CHR17Q12_REGION_DEFAULT = {
  chromosome: '17',
  cytoBand: '17q12',
  start: 36000000,
  end: 39900000,
  size: 3900000,
  name: '17q12 extended region (chr17:36.0-39.9 Mb)',
  assembly: 'GRCh38/hg38',
};

/**
 * HNF1B gene boundaries for visualization
 */
export const HNF1B_GENE_BOUNDARIES = {
  start: 37680000, // Adjusted to show actual variant positions
  end: 37750000, // 70kb range covering all HNF1B coding variants
};

/**
 * Get exon color based on domain
 * @param {Object} exon - Exon object with domain property
 * @returns {string} Hex color code
 */
export function getExonColor(exon) {
  if (exon.domain?.includes('POU')) return '#42A5F5'; // Blue
  if (exon.domain?.includes('Transactivation')) return '#66BB6A'; // Green
  if (exon.domain?.includes('UTR')) return '#BDBDBD'; // Grey
  return '#1E88E5'; // Default blue
}

/**
 * Get CNV color based on type
 * @param {string} cnvType - CNV type (DEL, DUP, etc.)
 * @returns {string} Hex color code
 */
export function getCNVColor(cnvType) {
  if (cnvType === 'DEL') return '#EF5350'; // Red for deletion
  if (cnvType === 'DUP') return '#42A5F5'; // Blue for duplication
  return '#9E9E9E'; // Grey for unknown
}

/**
 * Format genomic coordinate with thousand separators
 * @param {number} pos - Genomic position
 * @returns {string} Formatted coordinate
 */
export function formatCoordinate(pos) {
  return parseInt(pos).toLocaleString();
}

/**
 * Format size in human-readable format (kb, Mb)
 * @param {number} size - Size in base pairs
 * @returns {string} Formatted size
 */
export function formatSize(size) {
  if (size >= 1000000) {
    return `${(size / 1000000).toFixed(2)} Mb`;
  }
  return `${(size / 1000).toFixed(0)} kb`;
}

/**
 * Check if variant is a CNV based on hg38 coordinates
 * @param {Object} variant - Variant object with hg38 field
 * @returns {boolean} True if variant is a CNV (>= 50bp)
 */
export function isVariantCNV(variant) {
  if (!variant || !variant.hg38) return false;
  const hasRangeNotation = /(\d+|X|Y|MT?):(\d+)-(\d+):/.test(variant.hg38);
  if (!hasRangeNotation) return false;

  const match = variant.hg38.match(/:(\d+)-(\d+):/);
  if (match) {
    const start = parseInt(match[1]);
    const end = parseInt(match[2]);
    const size = end - start;
    return size >= 50;
  }
  return false;
}

/**
 * Check if variant is a small indel (< 50bp)
 * @param {Object} variant - Variant object with hg38 field
 * @returns {boolean} True if variant is a small indel
 */
export function isVariantIndel(variant) {
  if (!variant || !variant.hg38) return false;

  // Check for range notation
  const hasRangeNotation = /(\d+|X|Y|MT?):(\d+)-(\d+):/.test(variant.hg38);
  if (hasRangeNotation) {
    const match = variant.hg38.match(/:(\d+)-(\d+):/);
    if (match) {
      const start = parseInt(match[1]);
      const end = parseInt(match[2]);
      const size = end - start;
      return size < 50;
    }
  }

  // Check for VCF-style indels
  const vcfMatch = variant.hg38.match(/chr(\d+|X|Y|MT?)-(\d+)-([A-Z]+)-([A-Z]+)/i);
  if (vcfMatch) {
    const ref = vcfMatch[3];
    const alt = vcfMatch[4];
    if (ref.length !== alt.length) {
      return true;
    }
  }

  return false;
}

/**
 * Check if variant is a splice site variant
 * @param {Object} variant - Variant object with transcript and protein fields
 * @returns {boolean} True if variant is a splice variant
 */
export function isVariantSpliceVariant(variant) {
  if (!variant) return false;

  const hasTranscript = variant.transcript && variant.transcript !== '-';
  const noProtein = !variant.protein || variant.protein === '-';
  const isSpliceSite = hasTranscript && /[+-]\d+/.test(variant.transcript);

  return hasTranscript && noProtein && isSpliceSite;
}

/**
 * Extract genomic position from variant HG38 field
 * @param {Object} variant - Variant object
 * @param {Function} getCNVDetailsFn - Function to get CNV details
 * @returns {number|null} Genomic position or null
 */
export function extractVariantPosition(variant, getCNVDetailsFn) {
  // For CNVs, return the midpoint
  if (isVariantCNV(variant)) {
    const details = getCNVDetailsFn ? getCNVDetailsFn(variant) : null;
    if (details) {
      return (parseInt(details.start) + parseInt(details.end)) / 2;
    }
  }

  // Parse from HG38 coordinate
  if (variant.hg38) {
    const snvMatch = variant.hg38.match(/chr\d+-(\d+)-/);
    if (snvMatch) return parseInt(snvMatch[1]);

    const cnvMatch = variant.hg38.match(/:(\d+)-(\d+):/);
    if (cnvMatch) return (parseInt(cnvMatch[1]) + parseInt(cnvMatch[2])) / 2;
  }

  return null;
}

/**
 * Get indel details from variant
 * @param {Object} variant - Variant object with hg38 field
 * @returns {Object|null} Indel details or null
 */
export function getIndelDetails(variant) {
  if (!variant || !variant.hg38) return null;

  // First try range notation
  const rangeMatch = variant.hg38.match(/(\d+|X|Y|MT?):(\d+)-(\d+):([A-Z]+)/);
  if (rangeMatch) {
    return {
      chromosome: rangeMatch[1],
      start: rangeMatch[2],
      end: rangeMatch[3],
      type: rangeMatch[4],
    };
  }

  // Try VCF-style
  const vcfMatch = variant.hg38.match(/chr(\d+|X|Y|MT?)-(\d+)-([A-Z]+)-([A-Z]+)/i);
  if (vcfMatch) {
    const pos = parseInt(vcfMatch[2]);
    const ref = vcfMatch[3];
    const alt = vcfMatch[4];

    let type = 'INDEL';
    let end = pos;

    if (ref.length > 1 && alt.length > 1 && ref.length !== alt.length) {
      type = 'INDEL';
      end = pos + ref.length - 1;
    } else if (ref.length > alt.length) {
      type = 'DEL';
      end = pos + ref.length - 1;
    } else if (alt.length > ref.length) {
      type = 'INS';
      end = pos + ref.length;
    } else if (ref !== alt && ref.length === alt.length) {
      type = 'SUB';
      end = pos + ref.length - 1;
    }

    return {
      chromosome: vcfMatch[1],
      start: pos.toString(),
      end: end.toString(),
      type: type,
    };
  }

  return null;
}
